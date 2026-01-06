
import requests
import shutil
import os
import json

# Configuration
# Read from env or use defaults matching database.py
ARANGODB_HOST = os.getenv("ARANGODB_HOST", "http://localhost:8529")
ARANGODB_USERNAME = "root"
ARANGODB_PASSWORD = "3946" # Password from database.py context
DB_NAME = "DB_DB"

MOUNT_POINT = "/dev-ops"
SERVICE_DIR = "foxx_service"
ZIP_NAME = "foxx_service.zip"

def install_foxx():
    print(f"Bundling {SERVICE_DIR}...")
    shutil.make_archive("foxx_service", 'zip', SERVICE_DIR)
    
    url = f"{ARANGODB_HOST}/_db/{DB_NAME}/_api/foxx"
    
    # 1. Check if service exists (to decide Install vs Replace)
    # We will just use 'replace' endpoint with overwrite logic if supported, or standard install.
    # The 'replace' endpoint is usually PUT /_api/foxx/service?mount=...
    # But clean install via install endpoint with mount param is standard.
    
    # Let's try to UNINSTALL first to be clean, ignoring errors
    try:
        call_url = f"{url}/service?mount={MOUNT_POINT}"
        requests.delete(call_url, auth=(ARANGODB_USERNAME, ARANGODB_PASSWORD))
        print("Removed existing service (if any).")
    except:
        pass

    # 2. INSTALL
    install_url = f"{url}?mount={MOUNT_POINT}"
    print(f"Installing to {install_url}...")
    
    with open(ZIP_NAME, 'rb') as f:
        response = requests.post(
            install_url, 
            data=f, 
            headers={'Content-Type': 'application/zip'},
            auth=(ARANGODB_USERNAME, ARANGODB_PASSWORD)
        )
        
    if response.status_code in [200, 201]:
        print("Foxx Service Installed Successfully!")
        print(f"Endpoint: {ARANGODB_HOST}/_db/{DB_NAME}{MOUNT_POINT}/developers")
    else:
        print(f"Failed to install: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    install_foxx()
