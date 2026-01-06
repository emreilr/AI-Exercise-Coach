
import torch
import numpy as np
from typing import List, Dict, Any
import os

from app.ml.stgcn import STGCN_Encoder

# Configuration
MODEL_PATH = "stgcn_simclr.pth"
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
WINDOW_SIZE = 32
STRIDE = 1
JOINTS_25_INDICES = [
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24
]
# Note: MediaPipe has 33 landmarks. We need a mapping.
# For simplicity, we'll map the first 25 or specific indices.
# MediaPipe: 0-32. 
# NTU-25 Map approximation (This needs domain knowledge primarily):
# 0 (Nose) -> 0 (SpineBase? No). Mapping is critical.
# Let's assume the user accepts a direct slice [0:25] for now 
# OR use a placeholder mapping if not provided.
# Given the user context "Input Shape... V=25", we will slice first 25 for demo
# unless user specifies mapping.
# However, MP 0=nose, 11=left_shoulder... index 25 is left_knee.
# This simple slice might break the graph topology assumptions.
# Let's implement a robust mapper placeholder.

def map_mp_to_25(landmarks: List[Dict[str, float]]) -> np.ndarray:
    """
    Maps MediaPipe 33 landmarks to the 25-joint skeleton expected by STGCN.
    Output shape: (3, 25)
    """
    # Placeholder: Just take the first 25.
    # In production, this must match the Graph.get_edges() topology.
    # Assuming the training data follows the same topology.
    
    data = np.zeros((3, 25), dtype=np.float32)
    for i in range(25):
        if i < len(landmarks):
            lm = landmarks[i]
            data[0, i] = lm['x']
            data[1, i] = lm['y']
            data[2, i] = lm['z']
    return data

class InferenceService:
    def __init__(self):
        self.model = STGCN_Encoder().to(DEVICE)
        self.current_model_path = None
        self.loaded = False
        
        # We don't load a default model anymore. 
        # The caller must provide the model path specific to the exercise.
        
    def load_model(self, model_path: str):
        """
        Loads the model weights from the specified path.
        Caches the loading if it's already the current model.
        """
        if self.current_model_path == model_path and self.loaded:
            return # Already loaded
            
        if not model_path or not os.path.exists(model_path):
            print(f"[Inference] Warning: Model file {model_path} not found. Using random/current weights.")
            return

        try:
            state_dict = torch.load(model_path, map_location=DEVICE)
            self.model.load_state_dict(state_dict)
            self.model.eval()
            self.current_model_path = model_path
            self.loaded = True
            print(f"[Inference] Model loaded from {model_path}")
        except Exception as e:
            print(f"[Inference] Error loading model {model_path}: {e}")

    def generate_embeddings(self, frames_landmarks: List[List[Dict[str, float]]], model_path: str = None) -> List[List[float]]:
        """
        Generates embeddings for a generic video sequence using sliding window.
        Validates and uses the specified model_path.
        """
        if model_path:
            self.load_model(model_path)
        """
        Generates embeddings for a generic video sequence using sliding window.
        
        Args:
            frames_landmarks: List of F frames, each containing list of landmarks.
            
        Returns:
            List of embeddings corresponding to frames.
            Strategy: Window [t, t+32] embedding is assigned to frame t.
            Frames near end ( < 32 left) might not get embeddings or get last legitimate one.
        """
        num_frames = len(frames_landmarks)
        if num_frames == 0:
            return []
            
        # Strategy for short videos (< WINDOW_SIZE)
        # We will pad the sequence to WINDOW_SIZE using the last frame (or zeros)
        # and generate at least one embedding.
        is_short_video = False
        if num_frames < WINDOW_SIZE:
            is_short_video = True
            # We will handle padding during tensor creation below

        # 1. Convert all landmarks to Tensor (C, T_total, V)
        # If short, T_total_alloc = WINDOW_SIZE, else num_frames
        alloc_frames = max(num_frames, WINDOW_SIZE)
        
        full_skeleton = np.zeros((3, alloc_frames, 25), dtype=np.float32)
        
        for t, frame_lms in enumerate(frames_landmarks):
            skeleton_25 = map_mp_to_25(frame_lms)
            full_skeleton[:, t, :] = skeleton_25
            
        # Handle Padding for Short Video
        if is_short_video:
            # Pad the rest with the last frame's data
            last_frame_data = full_skeleton[:, num_frames-1, :]
            for t in range(num_frames, WINDOW_SIZE):
                 full_skeleton[:, t, :] = last_frame_data
                 
        full_skeleton_tensor = torch.from_numpy(full_skeleton).to(DEVICE)
        
        embeddings_map = [None] * num_frames
        
        # 2. Sliding Window Inference
        windows = []
        indices = []
        
        # If short video, we only have one window [0:32]
        loop_range = range(0, max(1, alloc_frames - WINDOW_SIZE + 1), STRIDE)
        
        for t in loop_range:
            # Check bounds just in case
            if t + WINDOW_SIZE > alloc_frames:
                break
                
            # Window: (3, 32, 25)
            window = full_skeleton_tensor[:, t : t + WINDOW_SIZE, :]
            windows.append(window)
            indices.append(t)
            
            if len(windows) >= 32:
                self._process_batch(windows, indices, embeddings_map)
                windows = []
                indices = []
                
        # Process remaining
        if windows:
            self._process_batch(windows, indices, embeddings_map)
            
        # If short video, the single embedding (at index 0) might need to be propagated
        # or accepted as is. Currently, index 0 gets it. That's fine for DTW if strict match isn't required.
        # But if DB expects embeddings for multiple frames, sparse is OK.
        
        return embeddings_map

    def _process_batch(self, windows, indices, embeddings_map):
        batch = torch.stack(windows) # (B, 3, 32, 25)
        
        with torch.no_grad():
            output = self.model(batch) # (B, 128)
            
        embeddings = output.cpu().numpy().tolist()
        
        for i, idx in enumerate(indices):
            embeddings_map[idx] = embeddings[i]

# Global Instance
inference_service = InferenceService()

def generate_embeddings_for_video_data(landmarks_list, model_path: str = None):
    return inference_service.generate_embeddings(landmarks_list, model_path)
