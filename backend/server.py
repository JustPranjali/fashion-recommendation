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

# Fashion item images mapping - Using reliable placeholder images
FASHION_IMAGES = {
    "Shirts": "https://via.placeholder.com/400x500/4A90E2/FFFFFF?text=Shirt",
    "Jeans": "https://via.placeholder.com/400x500/2E86AB/FFFFFF?text=Jeans", 
    "T-shirts": "https://via.placeholder.com/400x500/F24236/FFFFFF?text=T-Shirt",
    "Casual Shirts": "https://via.placeholder.com/400x500/7B68EE/FFFFFF?text=Casual+Shirt",
    "Dresses": "https://via.placeholder.com/400x500/FF69B4/FFFFFF?text=Dress",
    "Track Pants": "https://via.placeholder.com/400x500/32CD32/FFFFFF?text=Track+Pants",
    "Casual Shoes": "https://via.placeholder.com/400x500/8B4513/FFFFFF?text=Shoes",
    "Handbags": "https://via.placeholder.com/400x500/DA70D6/FFFFFF?text=Handbag",
    "Watches": "https://via.placeholder.com/400x500/FFD700/000000?text=Watch",
    "Heels": "https://via.placeholder.com/400x500/DC143C/FFFFFF?text=Heels",
    "Leather Belts": "https://via.placeholder.com/400x500/654321/FFFFFF?text=Belt",
    "Sneakers": "https://via.placeholder.com/400x500/00CED1/FFFFFF?text=Sneakers",
    "Blazers": "https://via.placeholder.com/400x500/191970/FFFFFF?text=Blazer",
    "Tops": "https://via.placeholder.com/400x500/FF1493/FFFFFF?text=Top",
    "Blouses": "https://via.placeholder.com/400x500/9370DB/FFFFFF?text=Blouse",
    "Polo": "https://via.placeholder.com/400x500/228B22/FFFFFF?text=Polo",
    "Hoodies": "https://via.placeholder.com/400x500/696969/FFFFFF?text=Hoodie",
    "Skirts": "https://via.placeholder.com/400x500/FF6347/FFFFFF?text=Skirt",
    "Shorts": "https://via.placeholder.com/400x500/20B2AA/FFFFFF?text=Shorts",
    "Sweaters": "https://via.placeholder.com/400x500/9932CC/FFFFFF?text=Sweater",
    "Chinos": "https://via.placeholder.com/400x500/D2691E/FFFFFF?text=Chinos",
    "Tank Tops": "https://via.placeholder.com/400x500/FF4500/FFFFFF?text=Tank+Top",
    "Henley": "https://via.placeholder.com/400x500/4682B4/FFFFFF?text=Henley",
    "Flats": "https://via.placeholder.com/400x500/DDA0DD/FFFFFF?text=Flats",
    "Sports Watches": "https://via.placeholder.com/400x500/000000/FFFFFF?text=Sports+Watch",
    "Leggings": "https://via.placeholder.com/400x500/800080/FFFFFF?text=Leggings",
    "Cardigans": "https://via.placeholder.com/400x500/B0C4DE/000000?text=Cardigan",
    "Jackets": "https://via.placeholder.com/400x500/8B0000/FFFFFF?text=Jacket",
    "default": "https://via.placeholder.com/400x500/708090/FFFFFF?text=Fashion+Item"
}

def get_item_image(article_type: str) -> str:
    """Get appropriate image for fashion item type"""
    return FASHION_IMAGES.get(article_type, FASHION_IMAGES["default"])

def remove_shadows_and_enhance(image):
    """Remove shadows and enhance skin tone detection using digital image processing"""
    # Convert to LAB color space for better shadow removal
    lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    
    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to L channel
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    l_enhanced = clahe.apply(l)
    
    # Merge back and convert to RGB
    enhanced_lab = cv2.merge([l_enhanced, a, b])
    enhanced_rgb = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2RGB)
    
    # Apply bilateral filter to reduce noise while preserving edges
    denoised = cv2.bilateralFilter(enhanced_rgb, 9, 75, 75)
    
    return denoised

def detect_skin_region_advanced(face_img):
    """Advanced skin detection excluding lips, eyes, hair using multiple methods"""
    h, w = face_img.shape[:2]
    
    # Method 1: YCbCr skin detection (more robust)
    ycbcr = cv2.cvtColor(face_img, cv2.COLOR_RGB2YCrCb)
    
    # Enhanced skin detection ranges in YCbCr
    lower_skin = np.array([0, 133, 77], dtype=np.uint8)
    upper_skin = np.array([255, 173, 127], dtype=np.uint8)
    skin_mask1 = cv2.inRange(ycbcr, lower_skin, upper_skin)
    
    # Method 2: HSV skin detection
    hsv = cv2.cvtColor(face_img, cv2.COLOR_RGB2HSV)
    lower_skin_hsv = np.array([0, 20, 70], dtype=np.uint8)
    upper_skin_hsv = np.array([20, 255, 255], dtype=np.uint8)
    skin_mask2 = cv2.inRange(hsv, lower_skin_hsv, upper_skin_hsv)
    
    # Method 3: RGB-based detection
    r, g, b = cv2.split(face_img)
    rgb_mask = ((r > 95) & (g > 40) & (b > 20) & 
                ((np.maximum(r, np.maximum(g, b)) - np.minimum(r, np.minimum(g, b))) > 15) &
                (np.abs(r.astype(int) - g.astype(int)) > 15) & 
                (r > g) & (r > b)).astype(np.uint8) * 255
    
    # Combine all masks
    combined_mask = cv2.bitwise_and(skin_mask1, skin_mask2)
    combined_mask = cv2.bitwise_and(combined_mask, rgb_mask)
    
    # Exclude eye and mouth regions (approximate locations)
    # Eyes are typically in the upper 1/3, mouth in lower 1/4
    eye_region_mask = np.ones_like(combined_mask)
    eye_region_mask[int(h*0.25):int(h*0.55), :] = 0  # Exclude eye region
    
    mouth_region_mask = np.ones_like(combined_mask)
    mouth_region_mask[int(h*0.75):, int(w*0.25):int(w*0.75)] = 0  # Exclude mouth region
    
    # Apply exclusion masks
    skin_mask_clean = cv2.bitwise_and(combined_mask, eye_region_mask)
    skin_mask_clean = cv2.bitwise_and(skin_mask_clean, mouth_region_mask)
    
    # Focus on cheek areas (most reliable for skin tone)
    cheek_mask = np.zeros_like(combined_mask)
    # Left cheek
    cheek_mask[int(h*0.4):int(h*0.7), int(w*0.1):int(w*0.4)] = 255
    # Right cheek  
    cheek_mask[int(h*0.4):int(h*0.7), int(w*0.6):int(w*0.9)] = 255
    # Forehead center
    cheek_mask[int(h*0.2):int(h*0.4), int(w*0.3):int(w*0.7)] = 255
    
    # Combine with skin detection
    final_mask = cv2.bitwise_and(skin_mask_clean, cheek_mask)
    
    # Morphological operations to clean up the mask
    kernel = np.ones((3,3), np.uint8)
    final_mask = cv2.morphologyEx(final_mask, cv2.MORPH_OPEN, kernel)
    final_mask = cv2.morphologyEx(final_mask, cv2.MORPH_CLOSE, kernel)
    
    return final_mask

def analyze_skin_tone_advanced(face_img, skin_mask):
    """Advanced skin tone analysis from masked region"""
    # Get skin pixels only
    skin_pixels = face_img[skin_mask > 0]
    
    if len(skin_pixels) < 100:
        # Fallback to center region if mask is too small
        h, w = face_img.shape[:2]
        center_region = face_img[int(h*0.3):int(h*0.7), int(w*0.3):int(w*0.7)]
        skin_pixels = center_region.reshape(-1, 3)
    
    # Remove outliers using IQR method
    def remove_outliers(data):
        q1 = np.percentile(data, 25, axis=0)
        q3 = np.percentile(data, 75, axis=0)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        mask = np.all((data >= lower_bound) & (data <= upper_bound), axis=1)
        return data[mask]
    
    cleaned_pixels = remove_outliers(skin_pixels)
    
    if len(cleaned_pixels) > 50:
        # Use median instead of mean for more robust estimation
        median_color = np.median(cleaned_pixels, axis=0).astype(int)
        return median_color
    else:
        return np.mean(skin_pixels, axis=0).astype(int)

def classify_skin_tone_detailed(rgb_color):
    """Detailed skin tone classification with undertones"""
    r, g, b = rgb_color
    
    # Calculate various color metrics
    brightness = (r + g + b) / 3
    
    # Undertone analysis
    red_ratio = r / max(g + b, 1)
    yellow_ratio = (r + g) / max(2 * b, 1)
    
    # Determine undertone
    if red_ratio > 1.1:
        undertone = "warm"
    elif yellow_ratio > 1.2:
        undertone = "warm"
    elif b > max(r, g):
        undertone = "cool"
    else:
        undertone = "neutral"
    
    # Classify depth
    if brightness > 200:
        depth = "Very Fair"
        if undertone == "cool":
            colors = ["Pastels", "White", "Lavender", "Light Blue", "Pink", "Silver"]
        else:
            colors = ["Cream", "Peach", "Coral", "Light Yellow", "Gold", "Warm White"]
    elif brightness > 170:
        depth = "Fair"
        if undertone == "cool":
            colors = ["Rose", "Berry", "Emerald", "Navy", "Purple", "Cool Gray"]
        else:
            colors = ["Warm Pink", "Coral", "Orange", "Yellow", "Camel", "Warm Brown"]
    elif brightness > 140:
        depth = "Light-Medium"
        if undertone == "cool":
            colors = ["Teal", "Sapphire", "Magenta", "Cool Red", "Black", "White"]
        else:
            colors = ["Rust", "Olive", "Warm Red", "Orange", "Gold", "Chocolate"]
    elif brightness > 110:
        depth = "Medium"
        if undertone == "cool":
            colors = ["Royal Blue", "Purple", "Pink", "Cool Green", "Black", "Gray"]
        else:
            colors = ["Burnt Orange", "Olive", "Warm Green", "Burgundy", "Gold", "Brown"]
    elif brightness > 80:
        depth = "Medium-Deep"
        if undertone == "cool":
            colors = ["Jewel Tones", "Purple", "Blue", "Pink", "Black", "White"]
        else:
            colors = ["Earth Tones", "Rust", "Orange", "Yellow", "Burgundy", "Camel"]
    else:
        depth = "Deep"
        if undertone == "cool":
            colors = ["Bright Colors", "Purple", "Blue", "Pink", "White", "Silver"]
        else:
            colors = ["Rich Colors", "Orange", "Red", "Yellow", "Gold", "Copper"]
    
    return f"{depth} ({undertone})", colors

def detect_skin_tone_advanced(face_img):
    """Enhanced skin tone detection using advanced digital image processing"""
    # Remove shadows and enhance the image
    enhanced_img = remove_shadows_and_enhance(face_img)
    
    # Detect skin regions while excluding non-skin areas
    skin_mask = detect_skin_region_advanced(enhanced_img)
    
    # Analyze skin tone from the clean mask
    skin_color = analyze_skin_tone_advanced(enhanced_img, skin_mask)
    
    return skin_color

def detect_skin_tone(image_bytes: bytes) -> tuple:
    """Enhanced skin tone detection with advanced image processing"""
    try:
        # Convert bytes to numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image format. Please use JPG, PNG, or GIF.")
        
        # Face detection with multiple scale factors
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply histogram equalization for better face detection
        gray_eq = cv2.equalizeHist(gray)
        
        # Try multiple detection parameters
        faces = face_cascade.detectMultiScale(gray_eq, 1.1, 5, minSize=(50, 50), maxSize=(500, 500))
        if len(faces) == 0:
            faces = face_cascade.detectMultiScale(gray, 1.05, 3, minSize=(30, 30))
        if len(faces) == 0:
            faces = face_cascade.detectMultiScale(gray, 1.3, 4, minSize=(80, 80))
            
        if len(faces) == 0:
            raise HTTPException(status_code=400, detail="No face detected. Please use a clear, well-lit photo showing your face clearly.")
        
        # Use the largest detected face
        largest_face = max(faces, key=lambda f: f[2] * f[3])
        x, y, w, h = largest_face
        
        # Crop face with minimal padding to focus on facial skin
        padding_x = int(w * 0.05)  # Reduced padding
        padding_y = int(h * 0.05)
        x1 = max(0, x + padding_x)
        y1 = max(0, y + padding_y)
        x2 = min(img.shape[1], x + w - padding_x)
        y2 = min(img.shape[0], y + h - padding_y)
        
        face_img = img[y1:y2, x1:x2]
        face_rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
        
        # Enhanced skin tone detection
        final_color = detect_skin_tone_advanced(face_rgb)
        
        # Convert to hex
        hex_color = "#{:02x}{:02x}{:02x}".format(*final_color)
        
        # Detailed classification
        skin_description, recommended_colors = classify_skin_tone_detailed(final_color)
        
        print(f"Advanced skin tone analysis: {skin_description}, RGB: {final_color}, Hex: {hex_color}")
        print(f"Recommended colors: {recommended_colors}")
        
        return hex_color, recommended_colors
        
    except Exception as e:
        print(f"Error in advanced skin tone detection: {e}")
        if "No face detected" in str(e) or "Invalid image" in str(e):
            raise e
        else:
            raise HTTPException(status_code=500, detail="Error processing image. Please try with a different photo with good lighting.")

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
        recommendations.append(recommendation.dict())
        # Add image URL to the recommendation
        recommendations[-1]['image_url'] = get_item_image(item['articleType'])
    
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