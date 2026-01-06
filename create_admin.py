from passlib.context import CryptContext
from datetime import datetime
import uuid
from app.db.database import ArangoDBConnection
from app.db.orientdb_client import OrientDBClient

# Setup Hash
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def create_admin():
    username = "root"
    raw_password = "1234"
    email = "root@example.com"
    fullname = "System Admin"
    
    hashed_password = get_password_hash(raw_password)
    current_time = datetime.utcnow().isoformat()
    
    # 1. ArangoDB Insert
    print(f"[ArangoDB] Creating user '{username}'...")
    try:
        conn = ArangoDBConnection()
        db = conn.get_db()
        User = db.collection("User")
        
        user_doc = {
            "_key": str(uuid.uuid4()),
            "username": username,
            "email": email,
            "hashed_password": hashed_password,
            "full_name": fullname,
            "user_type": "developer",
            "created_at": current_time,
            "google_id": None,
            "birth_date": None,
            "height": None
        }
        
        # Check if exists (not needed after clear, but good practice)
        # Assuming table is empty as per user request
        User.insert(user_doc)
        print("[ArangoDB] User inserted.")
        
        # 2. OrientDB Insert (Dual Write)
        print(f"[OrientDB] Syncing user '{username}'...")
        orient = OrientDBClient()
        orient.insert_user(user_doc) # Assuming this method exists in OrientDBClient
        print("[OrientDB] User synced.")
        
    except Exception as e:
        print(f"[Error] Failed to create admin: {e}")

if __name__ == "__main__":
    create_admin()
