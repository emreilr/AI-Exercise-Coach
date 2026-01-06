
import os
import uuid
import aiofiles
import magic
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, status, Depends
from typing import Optional

from app.routers.auth import get_current_user

from app.services.scoring import evaluate_session
from app.services.ingestion import process_video

# Helper wrapper for background task
def process_and_evaluate(video_path: str, user_id: str, exercise_id: str, model_path: str, video_id: str):
    # 1. Ingest & Embed (using the specific model)
    process_video(video_path, user_id, exercise_id, is_reference=False, model_path=model_path, video_id=video_id)
    
    # 2. Score
    try:
        # We need the video_id that was generated inside process_video.
        # However, process_video generates a random UUID inside.
        # Refactor: process_video should ideally take a video_id or return it.
        # But for now, we know the video_id is the basename of the file without extension if we force it,
        # OR we can assume `process_video` uses a predictable ID.
        # Looking at ingestion.py: video_uuid = str(uuid.uuid4())
        # This is a problem. The caller doesn't know the ID.
        #
        # IMPROVEMENT: Let's refactor process_video to return the ID or accept it?
        # Background tasks can't return values.
        # FIX: We will change `process_video` signature to accept `video_id` so we can control it here.
        print(f"[Scoring] Evaluating session for video {video_id}...")
        result = evaluate_session(user_video_id=video_id, exercise_id=exercise_id)
        print(f"[Scoring] Session Complete! ")
    except Exception as e:
        print(f"[Scoring] Error during evaluation: {e}")


from app.db.database import ArangoDBConnection

router = APIRouter()

# Configuration
UPLOAD_DIR = "uploaded_videos"
MAX_FILE_SIZE = 100 * 1024 * 1024 # 100 MB
ALLOWED_MIME_TYPES = ["video/mp4", "video/quicktime", "video/x-msvideo"]

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_video(
    background_tasks: BackgroundTasks,
    exercise_name: str = Form(...),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Endpoint to upload a video file for processing.
    
    - Validates file size and type.
    - Checks if a trained Model exists for the exercise.
    - Saves the file.
    - Triggers background processing AND Evaluates Score.
    """
    
    # Extract user_id from token
    user_id = current_user["_key"]

    db = ArangoDBConnection().get_db()
    
    # 0. Resolve Exercise Name to ID
    aql = "FOR e IN Exercise FILTER e.name == @name RETURN e"
    cursor = db.aql.execute(aql, bind_vars={"name": exercise_name})
    if cursor.empty():
         raise HTTPException(status_code=400, detail=f"Exercise '{exercise_name}' not found")
    exercise = cursor.next()
    exercise_id = exercise["_key"]

    # 0.5 Check for Trained Model
    aql_model = """
    FOR m IN Model
        FILTER m.exercise_id == @eid
        SORT m.created_at DESC
        LIMIT 1
        RETURN m
    """
    model_cursor = db.aql.execute(aql_model, bind_vars={"eid": exercise_id})
    if model_cursor.empty():
         raise HTTPException(status_code=400, detail=f"No trained model available for exercise '{exercise_name}'.")
    
    model = model_cursor.next()
    model_path = model["model_path"] # e.g. "stgcn_simclr.pth"

    # 1. Size Validation (Check Content-Length header first as a quick reject)
    # Note: Content-Length can be spoofed, so we also check actual read size if strictly needed.
    # For now, we trust the header for the initial check or read manually.
    # Since UploadFile is a SpooledTemporaryFile, checking size might require seeking.
    # We will check size during read/write to be safe.
    
    # 2. Magic Number Validation (Read first 2KB)
    try:
        header = await file.read(2048)
        mime_type = magic.from_buffer(header, mime=True)
        await file.seek(0) # Reset cursor
        
        if mime_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type: {mime_type}. Allowed: {ALLOWED_MIME_TYPES}"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error validating file: {str(e)}"
        )

    # 3. Generate Secure Filename
    file_extension = os.path.splitext(file.filename)[1]
    if not file_extension:
        # Fallback based on mime
        if mime_type == "video/mp4": file_extension = ".mp4"
        elif mime_type == "video/quicktime": file_extension = ".mov"
        elif mime_type == "video/x-msvideo": file_extension = ".avi"
        
    file_id = str(uuid.uuid4())
    secure_filename = f"{file_id}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, secure_filename)

    # 4. Save File with Size Limit Check
    try:
        size = 0
        async with aiofiles.open(file_path, 'wb') as out_file:
            while content := await file.read(1024 * 1024): # Read 1MB chunks
                size += len(content)
                if size > MAX_FILE_SIZE:
                    # Cleanup and reject
                    file.file.close()
                    os.remove(file_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum size of {MAX_FILE_SIZE} bytes."
                    )
                await out_file.write(content)
                
    except HTTPException:
        raise # Re-raise known errors
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )

    
    # Pass generated file_id as the video_id for DB consistency
    
    background_tasks.add_task(process_and_evaluate, file_path, user_id, exercise_id, model_path, file_id)

    return {
        "file_id": file_id,
        "message": "Video accepted. Scoring in progress...",
        "status": "processing"
    }
