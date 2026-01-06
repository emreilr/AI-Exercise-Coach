import requests
import json
import base64
import os
from datetime import datetime, date

class OrientDBClient:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OrientDBClient, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # Default config or from Environment
        self.host = "localhost"
        self.port = 2480
        self.user = "root"
        self.password = "3946"
        self.db_name = "OrientDB"
        self.base_url = f"http://{self.host}:{self.port}"
        
        # Use a Session for connection pooling
        self.session = requests.Session()
        # Initialize connection/auth header if needed, or just set headers
        # Note: requests.Session() persists cookies, but we use Basic Auth header.
        # We can pre-set the auth header.
        
        credentials = f"{self.user}:{self.password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        self.session.headers.update({
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json;charset=UTF-8"
        })
    
    # Remove _get_headers as we set it in session
    
    def command(self, sql: str):
        """Executes a SQL command against the configured database."""
        url = f"{self.base_url}/command/{self.db_name}/sql"
        try:
            # Use self.session
            response = self.session.post(url, data=sql.encode('utf-8'))
            if response.status_code == 200:
                try:
                    return response.json()
                except:
                    # Some commands might not return JSON (e.g. simple OK)
                    return {} 
            else:
                print(f"[OrientDB] Error {response.status_code}: {response.text}")
                return None
        except Exception as e:
            print(f"[OrientDB] Connection failed: {e}")
            return None

    def batch(self, operations: list):
        """
        Executes a batch of operations in a transaction.
        operations: list of dicts defining operations (type: 'c', record: {...})
        """
        url = f"{self.base_url}/batch/{self.db_name}"
        payload = {
            "transaction": True,
            "operations": operations
        }
        
        try:
            response = self.session.post(url, json=payload)
            if response.status_code == 200:
                return response.json()
            else:
                 print(f"[OrientDB] Batch Error {response.status_code}: {response.text}")
                 return None
        except Exception as e:
            print(f"[OrientDB] Batch Connection failed: {e}")
            return None


    def insert_user(self, user_doc: dict):
        # Wrapper for create_vertex specialized for User if needed, or just alias
        return self.create_vertex("User", user_doc)

    def create_vertex(self, class_name: str, properties: dict):
        """
        Generic method to create a vertex of a specific class.
        """
        # Serialize properties to JSON
        # Handle datetime objects
        def json_serial(obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            if isinstance(obj, bytes):
                 return base64.b64encode(obj).decode('utf-8')
            raise TypeError (f"Type {type(obj)} not serializable")
            
        json_data = json.dumps(properties, default=json_serial)
        
        # Syntax: INSERT INTO Class CONTENT { ... }
        sql = f"INSERT INTO {class_name} CONTENT {json_data}"
        return self.command(sql)

    def create_edge(self, edge_class: str, from_class: str, from_key: str, to_class: str, to_key: str, properties: dict = None):
        """
        Creates an edge between two vertices.
        Assumes vertices identify themselves via a property named '_key' (matching Arango),
        OR we can search by another unique field.
        """
        # We assume the vertices were inserted with their Arango '_key' preserved as a property called '_key'.
        
        from_query = f"(SELECT FROM {from_class} WHERE _key = '{from_key}')"
        to_query = f"(SELECT FROM {to_class} WHERE _key = '{to_key}')"
        
        sql = f"CREATE EDGE {edge_class} FROM {from_query} TO {to_query}"
        
        if properties:
            def json_serial(obj):
                if isinstance(obj, (datetime, datetime.date)):
                    return obj.isoformat()
                raise TypeError (f"Type {type(obj)} not serializable")
            
            json_data = json.dumps(properties, default=json_serial)
            sql += f" CONTENT {json_data}"
            
        return self.command(sql)
