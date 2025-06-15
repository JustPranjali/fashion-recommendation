from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timedelta
import pandas as pd
import cv2
import numpy as np
from sklearn.cluster import KMeans
import jwt
from passlib.context import CryptContext
import io
from PIL import Image
import base64

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Security
SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-secret-key-here')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Load fashion dataset
try:
    styles_df = pd.read_csv(ROOT_DIR / "styles.csv")
    print(f"✅ Loaded {len(styles_df)} fashion items")
except Exception as e:
    print(f"⚠️ Could not load styles.csv: {e}")
    styles_df = pd.DataFrame()

# Skin tone to color mapping
SKIN_TONE_TO_COLOR_MAPPING = {
    "#373028": ["Navy Blue", "Black", "Charcoal", "Burgundy", "Olive"],
    "#E5C8A6": ["Teal", "Pink", "Red", "Cream", "Gold"],
    "#FBF2F3": ["Pastels", "White", "Lavender", "Light Blue"],
    "#BEA07E": ["Sea Green", "Turquoise", "Peach", "Rose", "White"],
    "#81654F": ["Beige", "Off White", "Sea Green", "Cream"]
}

# Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserCreate(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class SkinToneAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    detected_skin_tone: str
    recommended_colors: List[str]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class OutfitRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    item_id: str
    product_name: str
    category: str
    sub_category: str
    article_type: str
    base_colour: str
    gender: str
    season: str
    usage: str

class Favorite(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    item_id: str
    product_name: str
    base_colour: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Utility functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        user = await db.users.find_one({"email": email})
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return User(**user)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

def closest_hex_color(hex_code: str, candidates: List[str]) -> str:
    """Find the closest hex color from candidates"""
    def hex_distance(h1: str, h2: str) -> float:
        h1_rgb = [int(h1[i:i+2], 16) for i in (1, 3, 5)]
        h2_rgb = [int(h2[i:i+2], 16) for i in (1, 3, 5)]
        return sum((c1 - c2) ** 2 for c1, c2 in zip(h1_rgb, h2_rgb))
    
    return min(candidates, key=lambda h: hex_distance(hex_code, h))

def detect_skin_tone(image_bytes: bytes) -> tuple:
    """Detect skin tone using K-means clustering"""
    try:
        # Convert bytes to numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Face detection
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        if len(faces) == 0:
            raise HTTPException(status_code=400, detail="No face detected in the image")
        
        # Crop face
        x, y, w, h = faces[0]
        face_img = img[y:y+h, x:x+w]
        face_rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
        resized_face = cv2.resize(face_rgb, (100, 100))
        
        # K-means clustering for dominant color
        pixels = resized_face.reshape((-1, 3))
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10).fit(pixels)
        dominant = kmeans.cluster_centers_[0].astype(int)
        hex_color = "#{:02x}{:02x}{:02x}".format(*dominant)
        
        # Find closest match and get recommendations
        available_hexes = list(SKIN_TONE_TO_COLOR_MAPPING.keys())
        closest_match = closest_hex_color(hex_color, available_hexes)
        recommended_colors = SKIN_TONE_TO_COLOR_MAPPING.get(closest_match, ["Black", "White", "Beige", "Cream"])
        
        return hex_color, recommended_colors
    except Exception as e:
        print(f"Error in skin tone detection: {e}")
        raise HTTPException(status_code=500, detail="Error processing image")

# Authentication routes
@api_router.post("/auth/signup", response_model=dict)
async def signup(user_data: UserCreate):
    # Check if user exists
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    user = User(email=user_data.email, hashed_password=hashed_password)
    await db.users.insert_one(user.dict())
    
    return {"message": "User created successfully"}

@api_router.post("/auth/login", response_model=Token)
async def login(user_data: UserLogin):
    user = await db.users.find_one({"email": user_data.email})
    if not user or not verify_password(user_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@api_router.get("/auth/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return {"email": current_user.email, "id": current_user.id}

# Skin tone and outfit recommendation routes
@api_router.post("/analyze-skin-tone")
async def analyze_skin_tone(
    file: UploadFile = File(...),
    current_user: Optional[User] = Depends(get_current_user)
):
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    image_bytes = await file.read()
    detected_color, recommended_colors = detect_skin_tone(image_bytes)
    
    # Save analysis
    analysis = SkinToneAnalysis(
        user_id=current_user.id if current_user else None,
        detected_skin_tone=detected_color,
        recommended_colors=recommended_colors
    )
    await db.skin_tone_analyses.insert_one(analysis.dict())
    
    return {
        "detected_skin_tone": detected_color,
        "recommended_colors": recommended_colors,
        "analysis_id": analysis.id
    }

@api_router.get("/outfit-recommendations")
async def get_outfit_recommendations(
    gender: str,
    recommended_colors: str,  # Comma-separated colors
    limit: int = 5
):
    if styles_df.empty:
        raise HTTPException(status_code=500, detail="Fashion dataset not available")
    
    colors_list = [color.strip() for color in recommended_colors.split(',')]
    
    # Filter by gender and recommended colors
    filtered_df = styles_df[
        (styles_df['gender'].str.lower() == gender.lower()) &
        (styles_df['baseColour'].isin(colors_list))
    ]
    
    if filtered_df.empty:
        # Fallback to any items for the gender
        filtered_df = styles_df[styles_df['gender'].str.lower() == gender.lower()]
    
    # Sample random items
    sample_size = min(limit, len(filtered_df))
    sampled_items = filtered_df.sample(n=sample_size) if sample_size > 0 else filtered_df
    
    recommendations = []
    for _, item in sampled_items.iterrows():
        recommendation = OutfitRecommendation(
            item_id=str(item['id']),
            product_name=item['productDisplayName'],
            category=item['masterCategory'],
            sub_category=item['subCategory'],
            article_type=item['articleType'],
            base_colour=item['baseColour'],
            gender=item['gender'],
            season=item['season'],
            usage=item['usage']
        )
        recommendations.append(recommendation)
    
    return {"recommendations": recommendations}

# Favorites routes
@api_router.post("/favorites")
async def add_to_favorites(
    item_id: str,
    product_name: str,
    base_colour: str,
    current_user: User = Depends(get_current_user)
):
    # Check if already in favorites
    existing = await db.favorites.find_one({
        "user_id": current_user.id,
        "item_id": item_id
    })
    if existing:
        raise HTTPException(status_code=400, detail="Item already in favorites")
    
    favorite = Favorite(
        user_id=current_user.id,
        item_id=item_id,
        product_name=product_name,
        base_colour=base_colour
    )
    await db.favorites.insert_one(favorite.dict())
    
    return {"message": "Added to favorites"}

@api_router.get("/favorites")
async def get_favorites(current_user: User = Depends(get_current_user)):
    favorites = await db.favorites.find({"user_id": current_user.id}).to_list(100)
    return {"favorites": favorites}

@api_router.delete("/favorites/{item_id}")
async def remove_from_favorites(
    item_id: str,
    current_user: User = Depends(get_current_user)
):
    result = await db.favorites.delete_one({
        "user_id": current_user.id,
        "item_id": item_id
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Favorite not found")
    
    return {"message": "Removed from favorites"}

# General routes
@api_router.get("/")
async def root():
    return {"message": "Fashion Recommendation API"}

@api_router.get("/fashion-categories")
async def get_fashion_categories():
    if styles_df.empty:
        return {"categories": []}
    
    categories = styles_df.groupby(['masterCategory', 'subCategory']).size().reset_index()
    category_data = []
    
    for _, row in categories.iterrows():
        category_data.append({
            "master_category": row['masterCategory'],
            "sub_category": row['subCategory'],
            "count": row[0]
        })
    
    return {"categories": category_data}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()