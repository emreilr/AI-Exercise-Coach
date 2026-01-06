import os
from typing import Optional
from arango import ArangoClient
from arango.database import StandardDatabase
from arango.http import DefaultHTTPClient


# Configuration
# We use os.getenv to allow overrides, but defaults are set to your specific requirements.
ARANGODB_HOST = os.getenv("ARANGODB_HOST", "http://localhost:8529")
ARANGODB_USERNAME = os.getenv("ARANGODB_USERNAME", "root")
ARANGODB_PASSWORD = os.getenv("ARANGODB_PASSWORD", "3946") # Updated Password
DB_NAME = os.getenv("DB_NAME", "DB_DB") # Updated Database Name

class ArangoDBConnection:
    """
    A Singleton class to handle ArangoDB connections with robust retry logic
    and connection pooling.
    """
    _instance: Optional["ArangoDBConnection"] = None
    _client: Optional[ArangoClient] = None
    _db: Optional[StandardDatabase] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ArangoDBConnection, cls).__new__(cls)
            cls._instance._initialize_client()
        return cls._instance

    def _initialize_client(self):
        """
        Initializes the ArangoClient with a custom HTTP client that supports
        automatic retries and connection pooling.
        """
        # 3. Initialize ArangoClient with the custom HTTP client
        # DefaultHTTPClient wraps the requests session, passing retry and pool options directly
        http_client = DefaultHTTPClient(
            retry_attempts=3,
            backoff_factor=1,
            pool_connections=10,
            pool_maxsize=10
        )
        
        print(f"[Database] Connecting to ArangoDB at {ARANGODB_HOST}...")
        self._client = ArangoClient(hosts=ARANGODB_HOST, http_client=http_client)

        # 5. Initialize the specific database connection
        self._connect_to_db()

    def _connect_to_db(self):
        """
        Connects to the system database to ensure the target database exists,
        then connects to the target database.
        """
        try:
            # Connect to _system database to check/create the target DB
            sys_db = self._client.db("_system", username=ARANGODB_USERNAME, password=ARANGODB_PASSWORD)

            if not sys_db.has_database(DB_NAME):
                print(f"[Database] Database '{DB_NAME}' not found. Creating it...")
                sys_db.create_database(DB_NAME)
            
            # Switch to the target database (DB_DB)
            self._db = self._client.db(DB_NAME, username=ARANGODB_USERNAME, password=ARANGODB_PASSWORD)
            print(f"[Database] Successfully connected to '{DB_NAME}'.")

        except Exception as e:
            print(f"[Database] Critical Connection Error: {e}")
            raise e

    def get_db(self) -> StandardDatabase:
        """
        Returns the active database instance.
        """
        if self._db is None:
            # Attempt reconnection if for some reason it's missing
            self._connect_to_db()
        return self._db

    def close(self):
        """
        Closes the underlying HTTP session.
        """
        if self._client:
            self._client.close()
            print("[Database] Connection closed.")