
import datetime
from typing import List, Optional, Dict
from app.db.database import ArangoDBConnection
from app.services.dtw_analysis import calculate_similarity

def get_video_embeddings(db, video_id: str) -> List[List[float]]:
    """
    Fetches the sequence of embeddings for a given video ID.
    Access based on keys usually needs frame iteration or AQL query.
    Using AQL to fetch all frame embeddings sorted by frame_number.
    """
    # Assuming video_id is the UUID
    aql = """
    FOR f IN Frame
        FILTER f.video_id == @video_id
        SORT f.frame_number ASC
        RETURN f.embeded_vector
    """
    cursor = db.aql.execute(aql, bind_vars={"video_id": video_id})
    embeddings = [emb for emb in cursor if emb is not None]
    return embeddings

def evaluate_session(user_video_id: str, exercise_id: str) -> Dict[str, any]:
    """
    Evaluates a user session by comparing the uploaded video against the exercise's reference video.
    
    Steps:
    1. Fetch user video embeddings.
    2. Identify reference video for the exercise.
    3. Fetch reference video embeddings.
    4. Calculate DTW similarity score.
    5. Save Session edge.
    
    Returns:
        Dict: {"score": float, "session_id": str}
    """
    db = ArangoDBConnection().get_db()

    # 1. Fetch User Embeddings
    user_embeddings = get_video_embeddings(db, user_video_id)
    if not user_embeddings:
        raise ValueError("User video has no processed embeddings yet.")

    # 2. Identify Reference Video
    # Query Exercise to get ref_video_id
    # Assuming Exercise document has 'ref_video_id' field as per summary/plan
    # Note: If schema is different, we might need to query Video with is_reference=true and exercise_id
    
    # Try finding explicit reference field first
    exercise_key = exercise_id
    if "/" in exercise_id:
        exercise_key = exercise_id.split("/")[-1]
        
    try:
        exercise_doc = db.collection("Exercise").get(exercise_key)
    except:
        exercise_doc = None
        
    ref_video_id = None
    if exercise_doc and "ref_video_id" in exercise_doc:
        ref_video_id = exercise_doc["ref_video_id"]
    
    # Fallback: Search for any reference video for this exercise
    if not ref_video_id:
        aql_ref = """
        FOR v IN Video
            FILTER v.exercise_id == @ex_id AND v.is_reference == true
            LIMIT 1
            RETURN v.video_id
        """
        cursor = db.aql.execute(aql_ref, bind_vars={"ex_id": exercise_id})
        for v_id in cursor:
            ref_video_id = v_id
            
    if not ref_video_id:
        raise ValueError(f"No reference video found for exercise {exercise_id}")

    # 3. Fetch Reference Embeddings
    ref_embeddings = get_video_embeddings(db, ref_video_id)
    if not ref_embeddings:
        raise ValueError(f"Reference video {ref_video_id} has no embeddings.")

    print(f"[Scoring] User Video ID: {user_video_id} (Frames: {len(user_embeddings)})")
    print(f"[Scoring] Ref Video ID:  {ref_video_id} (Frames: {len(ref_embeddings)})")

    # 4. Calculate Score
    score = calculate_similarity(user_embeddings, ref_embeddings)
    print(f"[Scoring] Calculated Score: {score}")
    
    # 5. Record Session
    # Create an edge from User -> Exercise (or Video -> Exercise?)
    # Prompt says: "Create a Session edge in ArangoDB: User -> Exercise"
    
    # Need user_id from the user_video
    video_doc = db.collection("Video").get(user_video_id)
    if not video_doc:
        raise ValueError("User video not found in DB.")
        
    user_id = video_doc["uploader_user_id"]
    # Ensure user_id is full handle if needed, usually db stores handle or we construct it
    # Ideally edges are _from: Collection/Key, _to: Collection/Key
    
    from_id = user_id if "/" in user_id else f"User/{user_id}"
    to_id = exercise_id if "/" in exercise_id else f"Exercise/{exercise_id}"
    
    session_data = {
        "_from": from_id,
        "_to": to_id,
        "score": score,
        "user_video_id": user_video_id,
        "ref_video_id": ref_video_id,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "model_type": "stgcn_simclr" 
    }
    
    # Insert edge
    # We might want to return the saved edge info
    # The collection is "Session" per init_db.py
    # NOTE: Session is an edge collection.
    
    edge_meta = db.collection("Session").insert(session_data)
    
    return {
        "score": score,
        "session_id": edge_meta["_id"],
        "user_video_id": user_video_id,
        "ref_video_id": ref_video_id
    }
