
import sys
import os

# Ensure the app directory is in the python path to import the database module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import ArangoDBConnection

def init_db():
    """
    Initializes the ArangoDB database with the required collections, indexes, 
    and schema validation rules.
    """
    print("Initializing Database Schema...")
    
    try:
        conn = ArangoDBConnection()
        db = conn.get_db()
        print(f"Connected to database: {db.name}")
    except Exception as e:
        print(f"Failed to connect to DB: {e}")
        return

    # ==========================================
    # 1. Define Collections & Schema Validation
    # ==========================================
    
    # 1. User
    # Fields: user_id (PK), full_name, username, email, hashed_password, 
    #         google_id, user_type, birth_date, height, created_at
    user_schema = {
        "rule": {
            "type": "object",
            "properties": {
                "full_name": {"type": "string"},
                "username": {"type": "string"},
                "email": {"type": "string"},
                "hashed_password": {"type": ["string", "null"]},
                "google_id": {"type": ["string", "null"]},
                "user_type": {"enum": ["patient", "developer"]},
                "birth_date": {"type": ["string", "null"]}, # ISO date string
                "height": {"type": ["number", "null"]},
                "created_at": {"type": "string"} # ISO date string
            },
            "required": ["full_name", "username", "email", "user_type", "created_at"]
        },
        "level": "moderate", # Warn on invalid, but allow (or 'strict' to reject)
        "message": "Start validation for User collection"
    }

    # 2. Exercise
    # Fields: exercise_id (PK), exercise_name, description, ref_video_id
    exercise_schema = {
        "rule": {
            "type": "object",
            "properties": {
                "exercise_name": {"type": "string"},
                "description": {"type": "string"},
                "ref_video_id": {"type": "string"}
            },
            "required": ["exercise_name"]
        },
        "level": "moderate",
        "message": "Start validation for Exercise collection"
    }

    # 3. Video
    # Fields: video_id (PK), uploader_user_id, exercise_id, upload_time, 
    #         fps, frame_count, embedding_dimension
    video_schema = {
        "rule": {
            "type": "object",
            "properties": {
                "uploader_user_id": {"type": "string"},
                "exercise_id": {"type": "string"},
                "upload_time": {"type": "string"},
                "fps": {"type": "number"},
                "frame_count": {"type": "integer"},
                "embedding_dimension": {"type": "integer"}
            },
            "required": ["uploader_user_id", "upload_time"]
        },
        "level": "moderate",
        "message": "Start validation for Video collection"
    }

    # 4. Frame
    # Fields: frame_id (PK), video_id, frame_number, timestamp, pose_landmark, embeded_vector
    frame_schema = {
        "rule": {
            "type": "object",
            "properties": {
                "video_id": {"type": "string"},
                "frame_number": {"type": "integer"},
                "timestamp": {"type": "number"},
                "pose_landmark": {
                    "type": "array",
                    # Simple validation that it's an array, complex inner validation can be expensive
                },
                "embeded_vector": {
                     "type": ["array", "null"],
                     "items": {"type": "number"} 
                }
            },
            "required": ["video_id", "frame_number", "timestamp"]
        },
        "level": "moderate",
        "message": "Start validation for Frame collection"
    }
    
    # 5. Model
    # Fields: model_id (PK), model_type, description, model_version, created_at, model_path, exercise_id
    model_schema = {
        "rule": {
            "type": "object",
            "properties": {
                "model_type": {"type": "string"},
                "description": {"type": "string"},
                "model_version": {"type": "string"},
                "created_at": {"type": "string"},
                "model_path": {"type": "string"},
                "exercise_id": {"type": "string"}
            },
            "required": ["model_type", "model_version", "model_path"]
        },
        "level": "moderate",
        "message": "Start validation for Model collection"
    }

    # 6. Session (Edge)
    # Fields: session_id (PK), _from, _to, score
    session_schema = {
        "rule": {
            "type": "object",
            "properties": {
                "score": {"type": "number", "minimum": 0, "maximum": 100}
            },
            "required": ["score"]
        },
        "level": "moderate",
        "message": "Start validation for Session collection"
    }

    # 7. FrameEdge (Edge)
    # Fields: _from, _to, edge_type
    frame_edge_schema = {
        "rule": {
            "type": "object",
            "properties": {
                "edge_type": {"enum": ["first", "next"]}
            },
            "required": ["edge_type"]
        },
        "level": "moderate",
        "message": "Start validation for FrameEdge collection"
    }

    collections_config = [
        {"name": "User", "type": "document", "schema": user_schema},
        {"name": "Exercise", "type": "document", "schema": exercise_schema},
        {"name": "Video", "type": "document", "schema": video_schema},
        {"name": "Frame", "type": "document", "schema": frame_schema},
        {"name": "Model", "type": "document", "schema": model_schema},
        {"name": "Session", "type": "edge", "schema": session_schema},
        {"name": "FrameEdge", "type": "edge", "schema": frame_edge_schema}
    ]

    for col in collections_config:
        name = col["name"]
        edge = (col["type"] == "edge")
        
        if not db.has_collection(name):
            print(f"Creating {col['type']} collection: {name}")
            # Note: create_collection with schema might need check_parameter=True in some versions,
            # but usually passed as 'schema' arg or via properties.
            # Python-arango create_collection signature supports schema.
            db.create_collection(name, edge=edge, schema=col.get("schema"))
        else:
            print(f"Collection {name} already exists. Updating schema...")
            # If exists, we can update the properties/schema
            try:
                c = db.collection(name)
                c.configure(schema=col.get("schema"))
                print(f" -> Schema updated for {name}")
            except Exception as e:
                print(f" -> Failed to update schema for {name}: {e}")

    # ==========================================
    # 2. Define Indexes (Same as before)
    # ==========================================
    print("Setting up indexes...")

    # --- User Collection ---
    user_col = db.collection("User")
    ensure_index(user_col, ["username"], unique=True)
    ensure_index(user_col, ["email"], unique=True)
    ensure_index(user_col, ["google_id"], unique=True, sparse=True)
    
    # --- Exercise Collection ---
    exercise_col = db.collection("Exercise")
    ensure_index(exercise_col, ["exercise_name"], unique=True)
    ensure_index(exercise_col, ["ref_video_id"])

    # --- Video Collection ---
    video_col = db.collection("Video")
    ensure_index(video_col, ["uploader_user_id"])
    ensure_index(video_col, ["exercise_id"])

    # --- Frame Collection ---
    frame_col = db.collection("Frame")
    ensure_index(frame_col, ["video_id"])
    ensure_index(frame_col, ["video_id", "frame_number"])
    ensure_index(frame_col, ["video_id", "timestamp"])

    # --- Model Collection ---
    model_col = db.collection("Model")
    ensure_index(model_col, ["exercise_id"])

    # --- Edge Indexes ---
    session_col = db.collection("Session")
    ensure_index(session_col, ["score"])
    
    frame_edge_col = db.collection("FrameEdge")
    ensure_index(frame_edge_col, ["edge_type"])

    print("Database initialization complete.")

def ensure_index(collection, fields, unique=False, sparse=False):
    """
    Helper to ensure a persistent index exists.
    """
    try:
        # add_index expects a dictionary configuration
        index_config = {
            "type": "persistent",
            "fields": fields,
            "unique": unique,
            "sparse": sparse
        }
        collection.add_index(index_config)
        print(f" -> Index ensured on {collection.name}: {fields} (Unique={unique}, Sparse={sparse})")
    except Exception as e:
        print(f" -> Error ensuring index on {collection.name} for {fields}: {e}")

if __name__ == "__main__":
    init_db()
