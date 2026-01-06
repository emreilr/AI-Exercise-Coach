
from fastapi import APIRouter, Depends, HTTPException, status, Response
from typing import List, Dict, Any, Optional
from app.routers.auth import get_current_user
from app.db.database import ArangoDBConnection
import csv
import io
import json

router = APIRouter()

def get_db():
    return ArangoDBConnection().get_db()

@router.get("/user/history")
async def get_user_history(current_user: dict = Depends(get_current_user)):
    """
    Returns the list of sessions for the current user.
    """
    user_id = current_user["_id"] # e.g., User/uuid
    
    db = get_db()
    # Query Session edges where _from is user_id
    # We also want to join with Exercise to get exercise name
    # and maybe Video to get video details?
    
    aql = """
    FOR s IN Session
        FILTER s._from == @user_id
        SORT s.timestamp DESC
        
        LET exercise = DOCUMENT(s._to)
        
        RETURN {
            "session_id": s._key,
            "timestamp": s.timestamp,
            "score": s.score,
            "exercise_name": exercise.name,
            "exercise_id": exercise._key,
            "video_id": s.user_video_id,
            "model_type": s.model_type
        }
    """
    
    cursor = db.aql.execute(aql, bind_vars={"user_id": user_id})
    history = [doc for doc in cursor]
    
    return history

@router.get("/user/history/export")
async def export_user_history(
    format: str = "json",
    current_user: dict = Depends(get_current_user)
):
    """
    Exports user history as CSV or JSON.
    """
    history = await get_user_history(current_user)
    
    if format.lower() == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(["Session ID", "Timestamp", "Score", "Exercise", "Video ID", "Model"])
        
        # Rows
        for item in history:
            writer.writerow([
                item["session_id"],
                item["timestamp"],
                f"{item['score']:.2f}",
                item.get("exercise_name", "Unknown"),
                item["video_id"],
                item.get("model_type", "")
            ])
            
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=history.csv"}
        )
        
    else:
        # JSON default
        return history

@router.get("/session/{session_id}/result")
async def get_session_result(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Returns detailed result for a single session.
    """
    db = get_db()
    
    # 1. Get Session
    # Session ID passed here might be just the key or full ID. ArangoDB _key.
    # Note: If it's just key, we need to know Collection. Session is edge collection.
    
    try:
        session = db.collection("Session").get(session_id)
    except:
        session = None
        
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # 2. Check Ownership
    # Session _from must match current_user._id
    if session["_from"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Not authorized to view this session")
        
    # 3. Construct Response
    # Fetch Exercise details
    exercise = db.document(session["_to"])
    
    # Generate Feedback
    score = session["score"]
    feedback = ""
    if score >= 90:
        feedback = "Excellent! Your form is almost perfect."
    elif score >= 70:
        feedback = "Good job! You are consistent, but watch the finer details."
    elif score >= 50:
        feedback = "Fair. Focus on keeping your movements smooth and aligned."
    else:
        feedback = "Needs improvement. Review the reference video and try again."
        
    result = {
        "session_id": session["_key"],
        "timestamp": session["timestamp"],
        "score": session["score"],
        "exercise_name": exercise["name"] if exercise else "Unknown",
        "feedback": feedback,
        "video_id": session["user_video_id"]
    }
    
    return result

@router.get("/user/stats/{exercise_id}")
async def get_user_exercise_stats(
    exercise_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Returns the user's statistics for a specific exercise:
    - Rank among all users
    - Personal Average Score
    - Global Average Score
    - Total Participants
    
    Uses COMPLEX QUERY (Aggregation, Window/Ranking Simulation, Subquery)
    """
    db = get_db()
    user_id = current_user["_id"]
    
    # We need to handle the ID format (Collection/Key vs Key)
    # If exercise_id passed is just the key, we might need to prefix?
    # Usually frontend passes ID from previous calls, let's assume raw key if not containing '/'
    
    # AQL:
    # 1. Group by User, Calculate Avg Score for this Exercise
    # 2. Sort by Avg Score DESC
    # 3. Use `COLLECT ... INTO ...` or array scan to find Rank
    
    aql = """
    LET exercise_key = @exercise_id
    
    // 1. Aggregate Stats Per User for this Exercise
    LET all_stats = (
        FOR s IN Session
            // Check if session links to this exercise (Edge: User -> Exercise, or stored property?)
            // Session schema: _from: User, _to: Exercise
            FILTER s._to == CONCAT('Exercise/', exercise_key) OR s._to == exercise_key
            
            COLLECT user = s._from AGGREGATE 
                avg_score = AVG(s.score),
                session_count = COUNT(s)
            
            SORT avg_score DESC
            RETURN { user, avg_score, session_count }
    )
    
    // 2. Calculate Global Stats
    LET global_avg = AVG(all_stats[*].avg_score)
    LET total_users = LENGTH(all_stats)
    
    // 3. Find Current User's Stats and Rank
    // We scan the sorted list. The index + 1 is the rank.
    
    LET user_stat_list = (
        FOR item IN all_stats
            FILTER item.user == @user_id
            RETURN item
    )
    
    LET user_stat = LENGTH(user_stat_list) > 0 ? user_stat_list[0] : null
    
    // Calculate Rank (Index in sorted list) - DISABLED
    
    RETURN {
        "personal_avg": user_stat ? user_stat.avg_score : 0,
        "session_count": user_stat ? user_stat.session_count : 0,
        "global_avg": global_avg != null ? global_avg : 0,
        "total_participants": total_users,
        "exercise_id": exercise_key
    }
    
    """

    try:
        cursor = db.aql.execute(aql, bind_vars={"exercise_id": exercise_id, "user_id": user_id})
        if cursor.empty():
             return {
                "personal_avg": 0,
                "session_count": 0,
                "global_avg": 0,

                "total_participants": 0,
                "exercise_id": exercise_id
            }
        return cursor.next()
    except Exception as e:
        print(f"[Stats Error] Failed to execute AQL: {e}")
        raise HTTPException(status_code=500, detail=str(e))
