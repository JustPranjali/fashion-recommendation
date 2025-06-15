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

# Fashion item images mapping
FASHION_IMAGES = {
    "Shirts": "https://images.unsplash.com/photo-1562157873-818bc0726f68",
    "Jeans": "https://images.unsplash.com/photo-1655362258669-e230aacbd21b", 
    "T-shirts": "https://images.pexels.com/photos/322207/pexels-photo-322207.jpeg",
    "Casual Shirts": "https://images.pexels.com/photos/5217841/pexels-photo-5217841.jpeg",
    "Dresses": "https://images.pexels.com/photos/985635/pexels-photo-985635.jpeg",
    "Track Pants": "https://images.unsplash.com/photo-1655362258669-e230aacbd21b",
    "Casual Shoes": "https://images.unsplash.com/photo-1560769629-975ec94e6a86",
    "Handbags": "https://images.unsplash.com/photo-1492707892479-7bc8d5a4ee93",
    "Watches": "https://images.unsplash.com/photo-1492707892479-7bc8d5a4ee93",
    "Heels": "https://images.pexels.com/photos/32552778/pexels-photo-32552778.jpeg",
    "Leather Belts": "https://images.unsplash.com/photo-1705873176985-85bb5788ef3a",
    "Sneakers": "https://images.unsplash.com/photo-1560769629-975ec94e6a86",
    "Blazers": "https://images.pexels.com/photos/5217841/pexels-photo-5217841.jpeg",
    "default": "https://images.pexels.com/photos/322207/pexels-photo-322207.jpeg"
}

def get_item_image(article_type: str) -> str:
    """Get appropriate image for fashion item type"""
    return FASHION_IMAGES.get(article_type, FASHION_IMAGES["default"])

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

def detect_skin_tone_ycbcr(face_img):
    """Enhanced skin tone detection using YCbCr color space"""
    # Convert to YCbCr color space
    ycbcr = cv2.cvtColor(face_img, cv2.COLOR_RGB2YCrCb)
    
    # Define skin tone ranges in YCbCr space
    # These ranges are more robust for different lighting conditions
    lower_skin = np.array([0, 133, 77], dtype=np.uint8)
    upper_skin = np.array([255, 173, 127], dtype=np.uint8)
    
    # Create mask for skin pixels
    skin_mask = cv2.inRange(ycbcr, lower_skin, upper_skin)
    
    # Get skin pixels
    skin_pixels = face_img[skin_mask > 0]
    
    if len(skin_pixels) > 100:  # Ensure we have enough skin pixels
        # Calculate mean RGB values of skin pixels
        mean_color = np.mean(skin_pixels, axis=0).astype(int)
        return mean_color
    else:
        # Fallback to center region if skin detection fails
        h, w = face_img.shape[:2]
        center_region = face_img[h//3:2*h//3, w//3:2*w//3]
        return np.mean(center_region.reshape(-1, 3), axis=0).astype(int)

def classify_skin_tone(rgb_color):
    """Classify skin tone into categories based on RGB values"""
    r, g, b = rgb_color
    
    # Calculate skin tone metrics
    brightness = (r + g + b) / 3
    redness = r - ((g + b) / 2)
    yellowness = (r + g) / 2 - b
    
    # Classify based on brightness and undertones
    if brightness > 200:
        return "Fair", ["Pastels", "White", "Lavender", "Light Blue", "Pink"]
    elif brightness > 160:
        return "Light", ["Teal", "Pink", "Red", "Cream", "Gold", "Coral"]
    elif brightness > 120:
        return "Medium", ["Sea Green", "Turquoise", "Peach", "Rose", "White", "Navy"]
    elif brightness > 80:
        return "Tan", ["Beige", "Off White", "Sea Green", "Cream", "Burgundy"]
    else:
        return "Deep", ["Navy Blue", "Black", "Charcoal", "Burgundy", "Olive", "Emerald"]

def detect_skin_tone(image_bytes: bytes) -> tuple:
    """Enhanced skin tone detection using multiple methods"""
    try:
        # Convert bytes to numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Face detection with multiple scale factors for better detection
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Try multiple parameters for better face detection
        faces = face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(30, 30))
        if len(faces) == 0:
            faces = face_cascade.detectMultiScale(gray, 1.05, 3, minSize=(20, 20))
        if len(faces) == 0:
            faces = face_cascade.detectMultiScale(gray, 1.3, 5, minSize=(50, 50))
            
        if len(faces) == 0:
            raise HTTPException(status_code=400, detail="No face detected in the image. Please use a clear photo with good lighting.")
        
        # Use the largest detected face
        largest_face = max(faces, key=lambda f: f[2] * f[3])
        x, y, w, h = largest_face
        
        # Crop face with some padding
        padding = int(min(w, h) * 0.1)
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(img.shape[1], x + w + padding)
        y2 = min(img.shape[0], y + h + padding)
        
        face_img = img[y1:y2, x1:x2]
        face_rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
        
        # Method 1: Enhanced YCbCr-based detection
        ycbcr_color = detect_skin_tone_ycbcr(face_rgb)
        
        # Method 2: Improved K-means clustering
        resized_face = cv2.resize(face_rgb, (150, 150))
        pixels = resized_face.reshape((-1, 3))
        
        # Remove outliers (very dark or very bright pixels)
        brightness = np.mean(pixels, axis=1)
        mask = (brightness > 30) & (brightness < 240)
        filtered_pixels = pixels[mask]
        
        if len(filtered_pixels) > 50:
            kmeans = KMeans(n_clusters=4, random_state=42, n_init=10).fit(filtered_pixels)
            centers = kmeans.cluster_centers_
            
            # Choose the cluster center that's most likely skin tone
            # (avoid very dark or very light clusters)
            skin_candidates = []
            for center in centers:
                brightness = np.mean(center)
                if 60 < brightness < 220:
                    skin_candidates.append(center)
            
            if skin_candidates:
                kmeans_color = min(skin_candidates, key=lambda c: abs(np.mean(c) - 140)).astype(int)
            else:
                kmeans_color = centers[0].astype(int)
        else:
            kmeans_color = ycbcr_color
        
        # Combine both methods for better accuracy
        final_color = ((ycbcr_color.astype(float) + kmeans_color.astype(float)) / 2).astype(int)
        
        # Convert to hex
        hex_color = "#{:02x}{:02x}{:02x}".format(*final_color)
        
        # Classify skin tone
        skin_type, recommended_colors = classify_skin_tone(final_color)
        
        print(f"Detected skin tone: {skin_type}, RGB: {final_color}, Hex: {hex_color}")
        
        return hex_color, recommended_colors
        
    except Exception as e:
        print(f"Error in skin tone detection: {e}")
        raise HTTPException(status_code=500, detail="Error processing image. Please try with a different photo.")

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