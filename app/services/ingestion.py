
import cv2
import mediapipe as mp
import uuid
import datetime
import os
import json
from typing import List, Dict, Any, Optional

from app.db.database import ArangoDBConnection

# Initialize MediaPipe Pose
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=1,
    smooth_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

def process_video(video_path: str, user_id: str, exercise_id: str):
    """
    Processes a video file to extract pose landmarks and ingests them into ArangoDB as a graph.
    
    Args:
        video_path: Path to the uploaded video file.
        user_id: ID of the user who uploaded the video.
        exercise_id: ID of the exercise being performed.
    """
    print(f"[Ingestion] Starting processing for video: {video_path}")
    
    if not os.path.exists(video_path):
        print(f"[Ingestion] Error: Video file not found at {video_path}")
        return

    # 1. Open Video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[Ingestion] Error: Could not open video file.")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # 2. Prepare Video Node Data
    video_uuid = str(uuid.uuid4())
    upload_time = datetime.datetime.utcnow().isoformat()
    
    video_doc = {
        "_key": video_uuid, # Use UUID as the key
        "video_id": video_uuid,
        "uploader_user_id": user_id,
        "exercise_id": exercise_id,
        "upload_time": upload_time,
        "fps": fps,
        "frame_count": total_frames,
        "embedding_dimension": 128 # Default as per requirements
    }
    
    # 3. Process Frames & Extract Landmarks
    frames_buffer = []
    edges_buffer = []
    
    frame_idx = 0
    previous_frame_id = None
    
    print(f"[Ingestion] Processing {total_frames} frames...")
    
    while cap.isOpened():
        success, image = cap.read()
        if not success:
            break
            
        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Process with MediaPipe
        results = pose.process(image_rgb)
        
        landmarks_data = []
        if results.pose_landmarks:
            for i, landmark in enumerate(results.pose_landmarks.landmark):
                landmarks_data.append({
                    "id": i,
                    "x": landmark.x,
                    "y": landmark.y,
                    "z": landmark.z,
                    "visibility": landmark.visibility
                })
        
        # Calculate timestamp (ms)
        timestamp_ms = (frame_idx / fps) * 1000
        
        # Create Frame Document
        # We use a deterministic key for frames: video_id + frame_idx
        # This makes edge creation easier without querying.
        frame_key = f"{video_uuid}_{frame_idx}"
        frame_id = f"Frame/{frame_key}"
        
        frame_doc = {
            "_key": frame_key,
            "video_id": video_uuid,
            "frame_number": frame_idx,
            "timestamp": timestamp_ms,
            "pose_landmark": landmarks_data,
            "embeded_vector": None # Placeholder
        }
        frames_buffer.append(frame_doc)
        
        # Create Edges
        if frame_idx == 0:
            # STARTS Edge: Video -> First Frame
            edge_doc = {
                "_from": f"Video/{video_uuid}",
                "_to": frame_id,
                "edge_type": "first"
            }
            edges_buffer.append(edge_doc)
        else:
            # NEXT Edge: Previous Frame -> Current Frame
            if previous_frame_id:
                edge_doc = {
                    "_from": previous_frame_id,
                    "_to": frame_id,
                    "edge_type": "next"
                }
                edges_buffer.append(edge_doc)
        
        previous_frame_id = frame_id
        frame_idx += 1
        
        if frame_idx % 100 == 0:
            print(f"[Ingestion] Processed {frame_idx}/{total_frames} frames")

    cap.release()
    print("[Ingestion] Video processing complete. Storing to Graph DB...")

    # 4. Ingest into ArangoDB (Bulk Import)
    try:
        db_conn = ArangoDBConnection()
        db = db_conn.get_db()
        
        # Insert Video Node
        # We insert single document for Video
        db.collection("Video").insert(video_doc)
        print(f"[Ingestion] Video node created: {video_uuid}")
        
        # Bulk Insert Frames
        if frames_buffer:
            db.collection("Frame").import_bulk(frames_buffer, on_duplicate="update")
            print(f"[Ingestion] Imported {len(frames_buffer)} frames.")
            
        # Bulk Insert Edges
        if edges_buffer:
            db.collection("FrameEdge").import_bulk(edges_buffer, on_duplicate="update")
            print(f"[Ingestion] Imported {len(edges_buffer)} frame edges.")
            
        print("[Ingestion] Data ingestion successful.")
        
    except Exception as e:
        print(f"[Ingestion] Database Error: {e}")
        # In a real system, we might want to clean up partial data or retry
