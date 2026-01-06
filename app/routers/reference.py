
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, BackgroundTasks, Depends
import aiofiles
import uuid
import os
import magic
from typing import Optional
from app.routers.auth import get_current_active_developer

from app.services.ingestion import process_video
from app.db.database import ArangoDBConnection

router = APIRouter()

UPLOAD_DIR = "uploaded_videos"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Helper wrapper
def process_and_update_ref(video_path: str, user_id: str, exercise_id: str, model_path: Optional[str], video_id: str):
    # 1. Ingest (and embed if model exists)
    process_video(video_path, user_id, exercise_id, is_reference=True, model_path=model_path, video_id=video_id)
    
    # 2. Update Exercise Document
    try:
        db = ArangoDBConnection().get_db()
        db.collection("Exercise").update({"_key": exercise_id, "ref_video_id": video_id})
        print(f"[Reference] Updated Exercise {exercise_id} with new ref_video_id: {video_id}")
    except Exception as e:
        print(f"[Reference] Failed to update Exercise ref_video_id: {e}")

@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_reference_video(
    background_tasks: BackgroundTasks,
    exercise_name: str = Form(...),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_active_developer)
):
    """
    Uploads a reference video for a specific exercise.
    - If a model exists, generates embeddings immediately.
    - Updates the Exercise document to point to this new reference video.
    """
    user_id = current_user["_key"]
    db = ArangoDBConnection().get_db()

    # 1.5. Resolve Exercise Name
    aql = "FOR e IN Exercise FILTER e.name == @name RETURN e"
    cursor = db.aql.execute(aql, bind_vars={"name": exercise_name})
    if cursor.empty():
         raise HTTPException(status_code=400, detail=f"Exercise '{exercise_name}' not found")
    exercise = cursor.next()
    exercise_id = exercise["_key"]

    # Check for Model (Optional for Reference, but good to have)
    aql_model = """
    FOR m IN Model
        FILTER m.exercise_id == @eid
        SORT m.created_at DESC
        LIMIT 1
        RETURN m.model_path
    """
    model_cursor = db.aql.execute(aql_model, bind_vars={"eid": exercise_id})
    model_path = model_cursor.next() if not model_cursor.empty() else None
    
    if model_path:
        print(f"[Reference] Found existing model: {model_path}. Embeddings will be generated.")
    else:
        print("[Reference] No existing model found. Embeddings will be skipped until training.")

    # 2. File Validation
    MAX_FILE_SIZE = 100 * 1024 * 1024 # 100MB
    try:
        # Check size
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File too large (max 100MB)")

        # Check type with magic
        header = await file.read(2048)
        await file.seek(0)
        mime = magic.Magic(mime=True)
        file_type = mime.from_buffer(header)
        
        if not file_type.startswith("video/"):
            raise HTTPException(status_code=415, detail="Invalid file type. Only videos are allowed.")
            
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=f"File validation failed: {str(e)}")

    # 3. Save File
    file_extension = os.path.splitext(file.filename)[1]
    if not file_extension:
        file_extension = ".mp4"
        
    unique_filename = f"{uuid.uuid4()}{file_extension}" 
    file_id = str(uuid.uuid4()) # Generate predictable ID for DB
    unique_filename = f"{file_id}{file_extension}"
    
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    try:
        async with aiofiles.open(file_path, 'wb') as out_file:
            while content := await file.read(1024 * 1024): # 1MB chunks
                await out_file.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

    # 4. Background Processing
    # Use process_and_update_ref wrapper
    background_tasks.add_task(process_and_update_ref, file_path, user_id, exercise_id, model_path, file_id)
    
    return {
        "file_id": file_id,
        "message": "Reference video accepted. Processing & Updating Exercise...",
        "status": "processing"
    }
