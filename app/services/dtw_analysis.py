
import numpy as np
from scipy.spatial.distance import cdist
from typing import List

def calculate_similarity(user_seq: List[List[float]], ref_seq: List[List[float]]) -> float:
    """
    Calculates the similarity score between a user's embedding sequence and a reference sequence.
    
    Algorithm:
    1. Dynamic Time Warping (DTW) to align the two temporal sequences.
    2. Distance Metric: Cosine Distance (1 - Cosine Similarity).
    3. Score Normalization: Exponential Decay.
    
    Args:
        user_seq: List of N embedding vectors (each 128-dim).
        ref_seq: List of M embedding vectors (each 128-dim).
        
    Returns:
        float: A normalized score between 0 and 100.
    """
    if not user_seq or not ref_seq:
        return 0.0

    # Convert to numpy arrays
    # Shape: (N, D) and (M, D)
    u_mat = np.array(user_seq, dtype=np.float32)
    r_mat = np.array(ref_seq, dtype=np.float32)
    
    # 1. Compute Distance Matrix (Cosine Distance)
    # Cosine Distance = 1 - Cosine Similarity
    # cdist returns distance matrix (N, M)
    dist_matrix = cdist(u_mat, r_mat, metric='cosine')
    
    # 2. Compute DTW alignment cost
    # Accumulated Cost Matrix
    n, m = dist_matrix.shape
    acc_cost = np.zeros((n, m))
    
    acc_cost[0, 0] = dist_matrix[0, 0]
    
    # Fill first row
    for j in range(1, m):
        acc_cost[0, j] = dist_matrix[0, j] + acc_cost[0, j-1]
        
    # Fill first column
    for i in range(1, n):
        acc_cost[i, 0] = dist_matrix[i, 0] + acc_cost[i-1, 0]
        
    # Fill rest
    for i in range(1, n):
        for j in range(1, m):
            acc_cost[i, j] = dist_matrix[i, j] + min(
                acc_cost[i-1, j],   # Insertion
                acc_cost[i, j-1],   # Deletion
                acc_cost[i-1, j-1]  # Match
            )
            
    # Total path cost
    total_cost = acc_cost[n-1, m-1]
    
    # Normalized Path Distance
    normalized_dist = total_cost / max(n, m)
    
    alpha = 3.0
    print(f"[DTW] Raw Normalized Distance: {normalized_dist:.4f} (Alpha={alpha})")

    # 3. Normalize Score (Exponential Decay)
    score = normalize_score(normalized_dist, alpha=alpha) # Increased strictness
    
    return score

def normalize_score(dist: float, alpha: float = 3.0) -> float:
    """
    Converts a raw distance into a 0-100 score using exponential decay.
    
    Score = 100 * e^(-alpha * distance)
    
    Args:
        dist: Raw normalized DTW distance.
        alpha: Decay parameter. 
               alpha=3.0: dist=0.1 -> 74, dist=0.5 -> 22, dist=1.0 -> 5
               Cosine distance is in [0, 2].
    """
    # Clip distance to be non-negative just in case
    d = max(0.0, dist)
    
    score = 100.0 * np.exp(-alpha * d)
    
    return float(score)
