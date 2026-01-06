
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Form
from typing import List, Optional
import uuid
import os

from app.routers.auth import get_current_active_developer, get_current_user
from app.db.database import ArangoDBConnection
from app.ml.train import train as run_training_pipeline
from app.services.inference import generate_embeddings_for_video_data, inference_service, map_mp_to_25
from app.services.ingestion import process_video
from app.utils.benchmark import run_arangodb_benchmark
import numpy as np

router = APIRouter()

@router.get("/benchmark")
async def benchmark(current_user: dict = Depends(get_current_active_developer)):
    """
    Runs ArangoDB benchmarks.
    """
    metrics = run_arangodb_benchmark()
    return metrics

def get_db():
    return ArangoDBConnection().get_db()

@router.post("/exercise", status_code=status.HTTP_201_CREATED)
async def create_exercise(
    name: str = Form(...),
    description: str = Form(""),
    ref_video_id: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_active_developer)
):
    """
    Creates a new Exercise type.
    """
    db = get_db()
    
    # Check for duplicates
    aql = "FOR e IN Exercise FILTER e.name == @name RETURN e"
    if not db.aql.execute(aql, bind_vars={"name": name}).empty():
        raise HTTPException(status_code=400, detail="Exercise already exists")
        
    exercise_doc = {
        "_key": str(uuid.uuid4()),
        "name": name,
        "description": description,
        "ref_video_id": ref_video_id 
    }
    
    db.collection("Exercise").insert(exercise_doc)
    return {"message": "Exercise created", "exercise_id": exercise_doc["_key"]}

# Global Status Store
training_status = {}

import datetime

@router.get("/train/status/{exercise_name}")
async def get_training_status(exercise_name: str, current_user: dict = Depends(get_current_active_developer)):
    """
    Returns the current training status for an exercise.
    """
    status = training_status.get(exercise_name, {"status": "idle", "message": "No training in progress", "progress": 0})
    return status

def train_and_update_reference(exercise_id: str, exercise_name: str):
    """
    Background Task (Sync):
    Runs in a threadpool to avoid blocking the main event loop during CPU-bound training.
    1. Triggers ML Training (SimCLR) with REAL DATA.
    2. Updates Reference Video embeddings.
    3. Saves Model Metadata.
    """
    print(f"[Admin] Starting training pipeline for exercise {exercise_name} ({exercise_id})...")
    
    # Initialize Status
    training_status[exercise_name] = {
        "status": "training",
        "message": "Fetching training data...",
        "progress": 0,
        "epoch": 0,
        "total_epochs": 25,
        "loss": 0.0
    }
    
    final_loss = 0.0
    final_epoch = 0
    
    db = get_db()
    
    # --- 1. Fetch Real Training Data ---
    training_data = []
    
    # Find all reference videos for this exercise
    aql_videos = """
    FOR v IN Video 
        FILTER v.exercise_id == @eid AND v.is_reference == true
        RETURN v
    """
    ref_videos = [v for v in db.aql.execute(aql_videos, bind_vars={"eid": exercise_id})]
    print(f"[Admin] Found {len(ref_videos)} reference videos for training.")
    
    for vid in ref_videos:
        vid_id = vid["video_id"] # or _key depending on schema, usually video_id field
        
        # Fetch Frames
        aql_frames = """
        FOR f IN Frame
            FILTER f.video_id == @vid
            SORT f.frame_number ASC
            RETURN f.pose_landmark
        """
        landmarks_list = [f for f in db.aql.execute(aql_frames, bind_vars={"vid": vid_id})]
        
        if not landmarks_list:
            continue
            
        # Convert to Numpy (3, T, 25)
        # map_mp_to_25 returns (3, 25)
        
        # Optimized stack
        T = len(landmarks_list)
        video_tensor = np.zeros((3, T, 25), dtype=np.float32)
        
        for t, lms in enumerate(landmarks_list):
            video_tensor[:, t, :] = map_mp_to_25(lms)
            
        training_data.append(video_tensor)
        
    print(f"[Admin] Prepared {len(training_data)} samples for training.")
    
    if not training_data:
        print("[Admin] No training data found! Aborting.")
        training_status[exercise_name] = {"status": "failed", "message": "No training data (reference videos) found.", "progress": 0}
        return

    def progress_callback(epoch, total, loss, msg):
        nonlocal final_loss, final_epoch
        final_loss = loss
        final_epoch = epoch
        
        training_status[exercise_name].update({
            "status": "training",
            "message": msg,
            "progress": int((epoch / total) * 100),
            "epoch": epoch,
            "total_epochs": total,
            "loss": loss
        })
    
    # --- 2. Train Model ---
    # Define unique model path
    models_dir = "trained_models"
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)
        
    model_filename = f"model_{exercise_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.pth"
    model_save_path = os.path.join(models_dir, model_filename)
    
    try:
        run_training_pipeline(training_data=training_data, progress_callback=progress_callback, save_path=model_save_path) 
        
        # Reload inference service model with this specific model
        # Note: If ingestion happens concurrently for other exercises, this global reload is risky.
        # But for this user flow, it ensures the newly trained model is active for the subsequent embedding update.
        inference_service.model.cpu() 
        import torch
        if os.path.exists(model_save_path):
             inference_service.model.load_state_dict(torch.load(model_save_path))
             inference_service.model.eval()
             print(f"[Admin] Inference model reloaded with new weights from {model_save_path}")
             
        training_status[exercise_name]["message"] = "Model trained. Updating embeddings..."
             
    except Exception as e:
        print(f"[Admin] Training failed: {e}")
        training_status[exercise_name] = {"status": "failed", "message": str(e), "progress": 0}
        return

    db = get_db()

    # 1.5 Save Model Metadata
    try:
        if not db.has_collection("Model"):
            db.create_collection("Model")
            
        model_doc = {
            "_key": str(uuid.uuid4()),
            "name": f"STGCN_SimCLR_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "model_type": "STGCN_SimCLR",
            "model_path": model_save_path, 
            "model_version": "1.0",
            "exercise_id": exercise_id,
            "final_loss": final_loss,
            "epochs_trained": final_epoch,
            "created_at": datetime.datetime.now().isoformat(),
            "description": f"Trained on {exercise_name} until epoch {final_epoch} with loss {final_loss:.4f}"
        }
        db.collection("Model").insert(model_doc)
        print(f"[Admin] Saved Model metadata: {model_doc['_key']}")
    except Exception as e:
        print(f"[Admin] Failed to save model metadata: {e}")

    # 2. Update Reference Video
    try:
        key = exercise_id.split("/")[-1] if "/" in exercise_id else exercise_id
        exercise = db.collection("Exercise").get(key)
    except:
        print(f"[Admin] Exercise {exercise_id} not found.")
        training_status[exercise_name] = {"status": "failed", "message": "Exercise not found during update", "progress": 0}
        return
        
    ref_video_id = exercise.get("ref_video_id")
    if not ref_video_id:
        aql = "FOR v IN Video FILTER v.exercise_id == @eid AND v.is_reference == true LIMIT 1 RETURN v.video_id"
        cursor = db.aql.execute(aql, bind_vars={"eid": exercise_id})
        for vid in cursor:
            ref_video_id = vid
            
    if not ref_video_id:
        print(f"[Admin] No reference video found for exercise {exercise_id}. Skipping embedding update.")
        training_status[exercise_name] = {"status": "completed", "message": "Training done. No reference video to update.", "progress": 100}
        return

    print(f"[Admin] Updating embeddings for reference video: {ref_video_id}")
    training_status[exercise_name]["message"] = f"Updating embeddings for Ref: {ref_video_id}..."
    
    # Fetch all frames/landmarks for this video
    aql_frames = """
    FOR f IN Frame
        FILTER f.video_id == @vid
        SORT f.frame_number ASC
        RETURN f
    """
    frames = [f for f in db.aql.execute(aql_frames, bind_vars={"vid": ref_video_id})]
    
    if not frames:
        print("[Admin] No frames found for reference video.")
    else:
        # Extract landmarks
        landmarks_list = [f.get("pose_landmark", []) for f in frames]
        
        # Generate Embeddings
        embeddings = generate_embeddings_for_video_data(landmarks_list)
        
        # Update Frames
        update_docs = []
        
        for i, emb in enumerate(embeddings):
            if emb is not None:
                doc = {"_key": frames[i]["_key"], "embeded_vector": emb}
                update_docs.append(doc)
                
        if update_docs:
            db.collection("Frame").import_bulk(update_docs, on_duplicate="update")
            print(f"[Admin] Updated {len(update_docs)} frames for reference video {ref_video_id}")
    
    print("[Admin] Training and Reference Update Complete.")
    training_status[exercise_name] = {
        "status": "completed", 
        "message": "Training & Updates Complete!", 
        "progress": 100, 
        "epoch": final_epoch,
        "total_epochs": 25,
        "loss": final_loss
    }

@router.get("/exercises")
async def list_exercises(current_user: dict = Depends(get_current_user)):
    """
    List all exercises.
    """
    db = get_db()
    cursor = db.collection("Exercise").all()
    exercises = [{"id": ex["_key"], "name": ex["name"]} for ex in cursor]
    return exercises

@router.post("/train", status_code=status.HTTP_202_ACCEPTED)
async def trigger_training(
    background_tasks: BackgroundTasks,
    exercise_name: str = Form(...),
    current_user: dict = Depends(get_current_active_developer)
):
    """
    Triggers the ML training pipeline and subsequently updates the reference video embeddings.
    Accepts exercise_name.
    """
    db = get_db()
    # Lookup ID
    aql = "FOR e IN Exercise FILTER e.name == @name RETURN e"
    cursor = db.aql.execute(aql, bind_vars={"name": exercise_name})
    if cursor.empty():
         raise HTTPException(status_code=404, detail=f"Exercise '{exercise_name}' not found")
    
    exercise = cursor.next()
    exercise_id = exercise["_key"]

    background_tasks.add_task(train_and_update_reference, exercise_id, exercise_name)
    return {"message": f"Training started for {exercise_name} in background.", "status": "training"}

@router.get("/user-activity")
async def get_user_activity(current_user: dict = Depends(get_current_active_developer)):
    """
    Returns a report of daily activity per user per exercise.
    Grouped by: User, Exercise, Date.
    """
    db = get_db()
    aql = """
    FOR s IN Session
        LET session_date = SUBSTRING(s.timestamp, 0, 10)
        // s._from is 'User/key', s._to is 'Exercise/key'
        COLLECT user_id = s._from, exercise_id = s._to, day = session_date WITH COUNT INTO count
        
        LET user = DOCUMENT(user_id)
        LET exercise = DOCUMENT(exercise_id)
        
        SORT day DESC, user.username ASC
        
        RETURN {
            "username": user.username,
            "exercise": exercise.name,
            "date": day,
            "count": count
        }
    """
    try:
        cursor = db.aql.execute(aql)
        return [doc for doc in cursor]
    except Exception as e:
        print(f"[Activity Report Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/developers")
async def list_developers(current_user: dict = Depends(get_current_active_developer)):
    """
    Lists all users with developer role.
    """
    db = get_db()
    aql = """
    FOR u IN User
        FILTER u.user_type == "developer"
        SORT u.created_at DESC
        RETURN {
            "username": u.username,
            "full_name": u.full_name,
            "email": u.email,
            "created_at": u.created_at,
            "is_verified": u.is_verified
        }
    """
    try:
        cursor = db.aql.execute(aql)
        return [doc for doc in cursor]
    except Exception as e:
        print(f"[List Developers Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/audit-logs")
async def get_audit_logs(current_user: dict = Depends(get_current_active_developer)):
    """
    Fetches the latest system audit logs (Foxx Triggers).
    """
    db = get_db()
    if not db.has_collection("AuditLog"):
        return []
        
    aql = """
    FOR a IN AuditLog
        SORT a.timestamp DESC
        LIMIT 100
        RETURN a
    """
    try:
        cursor = db.aql.execute(aql)
        return [doc for doc in cursor]
    except Exception as e:
        print(f"[Audit Log Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))
