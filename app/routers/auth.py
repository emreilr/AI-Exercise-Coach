
from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from starlette.config import Config
from starlette.requests import Request
from starlette.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
import os
import uuid
import csv
import codecs
import random
import string

from app.db.database import ArangoDBConnection
from app.db.orientdb_client import OrientDBClient
from app.services.email import send_verification_email

# Configuration
SECRET_KEY = "CHANGE_THIS_IN_PRODUCTION_SECRET"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# OAuth Config (Replace with environment variables in prod)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "mock-client-id")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "mock-client-secret")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

router = APIRouter()

# Initialize OAuth
config_data = {'GOOGLE_CLIENT_ID': GOOGLE_CLIENT_ID, 'GOOGLE_CLIENT_SECRET': GOOGLE_CLIENT_SECRET}
starlette_config = Config(environ=config_data)
oauth = OAuth(starlette_config)
oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# --- Utility Functions ---

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

def get_db():
    return ArangoDBConnection().get_db()

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        user_type: str = payload.get("user_type")
    except JWTError:
        raise credentials_exception
        
    db = get_db()
    
    aql = "FOR u IN User FILTER u.username == @username RETURN u"
    cursor = db.aql.execute(aql, bind_vars={"username": username})
    user = None
    if cursor.empty():
         aql = "FOR u IN User FILTER u.email == @username RETURN u"
         cursor = db.aql.execute(aql, bind_vars={"username": username})
         if cursor.empty():
             raise credentials_exception
    
    for u in cursor:
        user = u
        break
        
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_developer(current_user: dict = Depends(get_current_user)):
    if current_user.get("user_type") != "developer":
        raise HTTPException(status_code=403, detail="Not authorized")
    return current_user

async def get_current_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("user_type") != "developer": 
        raise HTTPException(status_code=403, detail="Not authorized")
    return current_user

# --- Endpoints ---

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup_patient(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    fullname: str = Form(...),
    birth_date: Optional[str] = Form(None),
    height: Optional[float] = Form(None)
):
    """
    Registers a new Patient account locally.
    Generates verification code and sends email.
    """
    db = get_db()
    
    # Check if exists
    aql = "FOR u IN User FILTER u.username == @username OR u.email == @email RETURN u"
    cursor = db.aql.execute(aql, bind_vars={"username": username, "email": email})
    if not cursor.empty():
        raise HTTPException(status_code=400, detail="Username or Email already registered")
        
    hashed_pw = get_password_hash(password)
    
    # Generate 6-digit code
    verification_code = ''.join(random.choices(string.digits, k=6))
    
    user_doc = {
        "_key": str(uuid.uuid4()), 
        "username": username,
        "email": email,
        "hashed_password": hashed_pw,
        "full_name": fullname,
        "birth_date": birth_date,
        "height": height,
        "user_type": "patient",
        "created_at": datetime.utcnow().isoformat(),
        
        # New Verification Fields
        "verification_code": verification_code,
        "is_verified": False
    }
    
    db.collection("User").insert(user_doc)
    
    # --- Dual Write to OrientDB ---
    try:
        orient_client = OrientDBClient()
        orient_client.insert_user(user_doc)
        print(f"[Info] User synced to OrientDB: {username}")
    except Exception as e:
        print(f"[Warning] Failed to sync to OrientDB: {e}")

    # --- Send Email ---
    await send_verification_email(email, verification_code)

    return {"message": "Patient created successfully. Please verify your email.", "require_verification": True}

@router.post("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(
    email: str = Form(...),
    code: str = Form(...)
):
    """
    Verifies user email with the code.
    """
    db = get_db()
    
    # Find user
    aql = "FOR u IN User FILTER u.email == @email RETURN u"
    cursor = db.aql.execute(aql, bind_vars={"email": email})
    
    user = None
    for u in cursor:
        user = u
        break
        
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user.get("is_verified"):
        return {"message": "User already verified"}
        
    # Check Code (No Expiry as requested)
    if user.get("verification_code") != code:
        raise HTTPException(status_code=400, detail="Invalid verification code")
        
    # Update Status
    user["is_verified"] = True
    user["verification_code"] = None # Clear code
    
    db.collection("User").update(user)
    
    # Sync status to OrientDB
    try:
        orient_client = OrientDBClient()
        # Find user and update
        # Assuming username is unique, we can use it to lookup for specific update or generic update query
        # Using a direct UPDATE command on fields is efficient
        sql = f"UPDATE User SET is_verified = true, verification_code = null WHERE email = '{email}'"
        orient_client.command(sql)
    except Exception as e:
        print(f"[Warning] Failed to update OrientDB verification status: {e}")
        
    return {"message": "Email verified successfully"}

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Local login. Returns JWT Access Token.
    Checks if user is verified.
    """
    db = get_db()
    
    # 1. Fetch User
    aql = "FOR u IN User FILTER u.username == @username RETURN u"
    cursor = db.aql.execute(aql, bind_vars={"username": form_data.username})
    user = None
    if cursor.empty():
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    for u in cursor:
        user = u
        break
        
    # 2. Verify Password
    if not verify_password(form_data.password, user.get("hashed_password")):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
        
    # 3. Check Verification
    if user.get("user_type") == "patient" and not user.get("is_verified", False):
        # We can block login or allow restricted access. Usually block.
        # Returning explicit error code useful for frontend redirect
        raise HTTPException(status_code=403, detail="Email not verified")

    # 4. Create Token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"], "user_type": user.get("user_type")},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/google/login")
async def login_google(request: Request):
    """
    Redirects to Google OAuth.
    """
    redirect_uri = request.url_for('auth_google_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/google/callback")
async def auth_google_callback(request: Request):
    """
    Handles Google Callback.
    """
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth Error: {e}")
        
    user_info = token.get('userinfo')
    if not user_info:
        # Depending on authlib version, might need to fetch manually
        user_info = await oauth.google.userinfo(token=token)
        
    email = user_info.get("email")
    google_id = user_info.get("sub")
    name = user_info.get("name")
    
    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email")
        
    db = get_db()
    
    # Check if user exists by email or google_id
    aql = "FOR u IN User FILTER u.email == @email OR u.google_id == @gid RETURN u"
    cursor = db.aql.execute(aql, bind_vars={"email": email, "gid": google_id})
    
    user = None
    if not cursor.empty():
        # User exists, link account if needed
        for u in cursor:
            user = u
            if not user.get("google_id"):
                # Link
                user["google_id"] = google_id
                db.collection("User").update(user)
            break
    else:
        # Create new Patient User
        # Username defaults to email for google users
        user_doc = {
            "_key": str(uuid.uuid4()),
            "username": email, # Fallback
            "email": email,
            "google_id": google_id,
            "full_name": name,
            "hashed_password": None, # No local password
            "birth_date": None,
            "height": None,
            "user_type": "patient",
            "created_at": datetime.utcnow().isoformat(),
            # Google verified implies verified usually, or force?
            "is_verified": True # Trust Google
        }
        meta = db.collection("User").insert(user_doc)
        user = user_doc
        user["_key"] = meta["_key"] # Update key
        
        # Sync to OrientDB
        try:
            orient_client = OrientDBClient()
            orient_client.insert_user(user_doc)
        except:
            pass
        
    # Issue JWT
    access_token = create_access_token(
        data={"sub": user["username"], "user_type": user["user_type"]}
    )
    
    # Redirect to Frontend with Token
    # Ideally, get frontend URL from env
    frontend_url = f"http://localhost:5173/auth/callback?token={access_token}"
    return RedirectResponse(url=frontend_url)

@router.post("/admin/create-developer", status_code=status.HTTP_201_CREATED)
async def create_developer(
    username: str = Form(...),
    password: str = Form(...),
    fullname: str = Form(""),
    current_user: dict = Depends(get_current_admin)
):
    """
    Creates a new Developer account via Foxx Stored Procedure.
    - Calls Foxx Endpoint: /dev-ops/developers
    - Triggers internal audit log automatically.
    """
    import requests
    from app.db.database import ARANGODB_HOST, DB_NAME, ARANGODB_USERNAME, ARANGODB_PASSWORD
    
    hashed_pw = get_password_hash(password)
    
    foxx_url = f"{ARANGODB_HOST}/_db/{DB_NAME}/dev-ops/developers"
    
    payload = {
        "username": username,
        "hashed_password": hashed_pw,
        "full_name": fullname
    }
    
    try:
        response = requests.post(
            foxx_url, 
            json=payload,
            auth=(ARANGODB_USERNAME, ARANGODB_PASSWORD)
        )
        
        if response.status_code != 200:
            # Parse error from Foxx
            error_data = response.json()
            # Foxx usually returns { error: true, errorMessage: "..." }
            # If we set statusCode in Foxx, it comes through response status.
            
            detail = error_data.get('errorMessage', response.text)
            
            # Remove technical prefixes if any (ArangoDB sometimes adds file path info in dev mode)
            # But 'errorMessage' set in Error object usually stays clean.
            
            # If it's the duplicate error (409 Conflict), clean it up
            if response.status_code == 409:
                 pass # Use detail as is ("Username is already taken.")
            
            raise HTTPException(status_code=response.status_code if response.status_code < 500 else 400, detail=detail)
            
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to call Foxx Service: {e}")

    return {"message": "Developer account created successfully via Foxx"}

@router.post("/admin/batch-create-developers", status_code=status.HTTP_200_OK)
async def batch_create_developers(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_admin)
):
    """
    Batch creates developer accounts from a CSV file.
    Expected columns: username, password, full_name
    """
    db = get_db()
    csvReader = csv.DictReader(codecs.iterdecode(file.file, 'utf-8'))
    
    success_count = 0
    errors = []
    
    for row in csvReader:
        # Normalize keys (strip whitespace)
        row = {k.strip(): v.strip() for k, v in row.items() if k}
        
        username = row.get("username")
        password = row.get("password")
        full_name = row.get("full_name") or row.get("fullname") or ""
        
        if not username or not password:
            errors.append(f"Row missing username or password: {row}")
            continue
            
        # Check duplicate
        aql = "FOR u IN User FILTER u.username == @username RETURN u"
        cursor = db.aql.execute(aql, bind_vars={"username": username})
        if not cursor.empty():
            errors.append(f"Username already exists: {username}")
            continue
            
        hashed_pw = get_password_hash(password)
        user_doc = {
            "_key": str(uuid.uuid4()),
            "username": username,
            "email": f"{username}@example.com",
            "hashed_password": hashed_pw,
            "full_name": full_name,
            "user_type": "developer",
            "created_at": datetime.utcnow().isoformat(),
            "is_verified": True
        }
        
        try:
            db.collection("User").insert(user_doc)
            success_count += 1
        except Exception as e:
            errors.append(f"Failed to insert {username}: {str(e)}")
            
    return {
        "message": f"Processed batch. Created: {success_count}. Failed: {len(errors)}",
        "errors": errors
    }

@router.get("/user/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    """
    Get current user profile.
    """
    # Remove sensitive data
    user_data = current_user.copy()
    user_data.pop("hashed_password", None)
    return user_data

@router.patch("/user/me")
async def update_profile(
    fullname: Optional[str] = Form(None),
    birth_date: Optional[str] = Form(None),
    height: Optional[float] = Form(None),
    password: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Update profile fields. Prevent changing username/email/google_id.
    """
    if current_user["user_type"] != "patient":
         # Or allow devs to update their profile too? Sure.
         pass
         
    updates = {}
    if fullname is not None:
        updates["full_name"] = fullname
    if birth_date is not None:
        updates["birth_date"] = birth_date
    if height is not None:
        updates["height"] = height
    if password is not None and password.strip():
        updates["hashed_password"] = get_password_hash(password)
        
    if not updates:
        return {"message": "No changes provided"}
        
    db = get_db()
    # current_user is the dict from DB (returned by get_current_user logic)
    # We need the key to update.
    # The AQL in get_current_user returns the document including _key and _id.
    
    updates["_key"] = current_user["_key"]
    db.collection("User").update(updates)
    
    return {"message": "Profile updated successfully", "updates": updates}
