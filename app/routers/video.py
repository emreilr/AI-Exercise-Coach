
import os
import uuid
import aiofiles
import magic
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, status
from typing import Optional

from app.services.ingestion import process_video

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
    user_id: str = Form(...),
    exercise_id: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Endpoint to upload a video file for processing.
    
    - Validates file size and type (magic numbers).
    - Saves the file asynchronously.
    - Triggers background processing.
    """
    
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

    # 5. Trigger Background Processing
    background_tasks.add_task(process_video, file_path, user_id, exercise_id)

    return {
        "file_id": file_id,
        "message": "Video accepted for processing.",
        "status": "processing"
    }

