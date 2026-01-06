
import requests
import json
import os
import time

# Configuration
ARANGODB_HOST = os.getenv("ARANGODB_HOST", "http://localhost:8529")
DB_NAME = "DB_DB"
MOUNT_POINT = "/dev-ops"
USERNAME = "root"
PASSWORD = "3946"

BASE_URL = f"{ARANGODB_HOST}/_db/{DB_NAME}{MOUNT_POINT}"

def verify():
    print("--- Verifying Foxx Service ---")
    
    # 0. Clean up (Direct AQL via System API)
    print("Cleaning up previous test data...")
    aql_url = f"{ARANGODB_HOST}/_db/{DB_NAME}/_api/cursor"
    headers = {"Content-Type": "application/json"}
    auth = (USERNAME, PASSWORD)
    
    cleanup_query = 'FOR u IN User FILTER u.username == "test_foxx_dev" REMOVE u IN User'
    requests.post(aql_url, json={"query": cleanup_query}, auth=auth)
    
    cleanup_audit = 'FOR a IN AuditLog FILTER a.action == "CREATE_DEVELOPER" AND CONTAINS(a.details, "test_foxx_dev") REMOVE a IN AuditLog'
    requests.post(aql_url, json={"query": cleanup_audit}, auth=auth)
    
    # 1. Create Developer via Foxx
    print("\n1. Testing POST /developers (Stored Procedure)...")
    create_url = f"{BASE_URL}/developers"
    payload = {
        "username": "test_foxx_dev",
        "hashed_password": "hashed_secret_123",
        "full_name": "Foxx Tester"
    }
    
    response = requests.post(create_url, json=payload, auth=auth)
    
    if response.status_code == 200:
        print(" [PASS] User creation request successful.")
    else:
        print(f" [FAIL] Request failed: {response.text}")
        return

    # 2. Verify User in DB
    print("\n2. Verifying User in Database...")
    check_user_query = 'FOR u IN User FILTER u.username == "test_foxx_dev" RETURN u'
    res = requests.post(aql_url, json={"query": check_user_query}, auth=auth)
    data = res.json()
    if data['result']:
        print(f" [PASS] User found in DB: {data['result'][0]['username']}")
    else:
        print(" [FAIL] User NOT found in DB!")

    # 3. Verify Trigger (Audit Log)
    print("\n3. Verifying Trigger (AuditLog)...")
    check_audit_query = 'FOR a IN AuditLog FILTER a.action == "CREATE_DEVELOPER" AND CONTAINS(a.details, "test_foxx_dev") RETURN a'
    res = requests.post(aql_url, json={"query": check_audit_query}, auth=auth)
    data = res.json()
    if data['result']:
        print(f" [PASS] Audit Log found: {data['result'][0]['details']}")
    else:
        print(" [FAIL] Audit Log NOT found! Trigger failed?")

    # 4. Verify Duplicate Prevention
    print("\n4. Verifying Duplicate Prevention...")
    response_dup = requests.post(create_url, json=payload, auth=auth)
    if response_dup.status_code == 409:
        print(f" [PASS] Duplicate rejected as expected (409 Conflict). Msg: {response_dup.json().get('errorMessage')}")
    else:
        print(f" [FAIL] Duplicate check failed! Status: {response_dup.status_code}, Msg: {response_dup.text}")

if __name__ == "__main__":
    verify()
