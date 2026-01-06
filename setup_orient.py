import requests
import json
import base64
import uuid
from datetime import datetime
from passlib.context import CryptContext

# --- AYARLAR ---
DB_HOST = "localhost" 
DB_PORT = 2480
DB_USER = "root"
DB_PASS = "3946" 
DB_NAME = "OrientDB" 

BASE_URL = f"http://{DB_HOST}:{DB_PORT}"

# Password Hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_auth_headers():
    credentials = f"{DB_USER}:{DB_PASS}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    return {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/json;charset=UTF-8"
    }

def command(sql):
    url = f"{BASE_URL}/command/{DB_NAME}/sql"
    headers = get_auth_headers()
    response = requests.post(url, headers=headers, data=sql.encode('utf-8'))
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Query failed: {response.status_code} - {response.text}")

def db_exists():
    url = f"{BASE_URL}/database/{DB_NAME}"
    headers = get_auth_headers()
    response = requests.get(url, headers=headers)
    return response.status_code == 200

def create_admin_user(username, email, password):
    print(f"\n Admin kullanıcısı oluşturuluyor: {username} ({email})")
    
    # 1. Check if user exists
    sql_check = f"SELECT FROM User WHERE username = '{username}' OR email = '{email}'"
    existing = command(sql_check)
    
    if existing.get('result'):
        print(f" (!) Kullanıcı '{username}' veya '{email}' zaten mevcut. Atlanıyor.")
        return

    # 2. Hash password
    hashed_pw = pwd_context.hash(password)
    
    # 3. Insert User
    # Note: OrientDB INSERT uses keys not columns if strictly SQL, but here we use SET for named fields.
    # Be careful with quotes in SQL strings.
    
    # Using JSON content is safer for complex fields but SQL INSERT SET is easier for simple fields.
    sql_insert = (
        f"INSERT INTO User SET "
        f"username = '{username}', "
        f"email = '{email}', "
        f"hashed_password = '{hashed_pw}', "
        f"fullname = 'Admin User', "
        f"user_type = 'developer', "
        f"created_at = '{datetime.utcnow().isoformat()}'"
    )
    
    try:
        command(sql_insert)
        print(" + Admin kullanıcısı başarıyla eklendi.")
    except Exception as e:
        print(f" - Admin ekleme hatası: {e}")

def create_schema():
    print(f" OrientDB'ye bağlanılıyor ({DB_HOST}:{DB_PORT})...")
    
    try:
        if not db_exists():
             print(f" Veritabanı '{DB_NAME}' bulunamadı! Lütfen önce oluşturun.")
             return
        
        print(f" Veritabanı bulundu: {DB_NAME}")

        schema = {
            "Exercise": "V",
            "Frame": "V",
            "Model": "V",
            "User": "V",
            "Video": "V",
            "FrameEdge": "E",
            "Session": "E"
        }

        print("\n Şema oluşturuluyor...")
        existing_classes_result = command("SELECT name FROM (SELECT expand(classes) FROM metadata:schema)")
        existing_classes = [r['name'] for r in existing_classes_result.get('result', [])]

        for class_name, class_type in schema.items():
            if class_name not in existing_classes:
                sql = f"CREATE CLASS {class_name} EXTENDS {class_type}"
                command(sql)
                type_label = "Vertex (Düğüm)" if class_type == "V" else "Edge (Bağlantı)"
                print(f"   Oluşturuldu: {class_name:<12} -> {type_label}")
            else:
                print(f"   Zaten var:   {class_name}")

        print("\n OrientDB şeması başarıyla kuruldu!")

        # --- ADMIN PROMPT ---
        print("\n--- Admin Kullanıcısı Ekleme ---")
        use_input = input("Admin eklemek ister misiniz? (E/h): ").lower()
        if use_input != 'h':
            u_name = input("Kullanıcı Adı [admin]: ").strip() or "admin"
            u_email = input("Email [admin@example.com]: ").strip() or "admin@example.com"
            u_pass = input("Şifre [admin]: ").strip() or "admin"
            
            create_admin_user(u_name, u_email, u_pass)
        else:
            print("Admin ekleme atlandı.")
            
        print("\nKurulum tamamlandı.")

    except Exception as e:
        print(f"\n Bir hata oluştu: {e}")

if __name__ == "__main__":
    create_schema()