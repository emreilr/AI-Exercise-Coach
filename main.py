from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Import Routers
from app.routers import video, reference, auth, dashboard, admin

app = FastAPI(
    title="Pose Analysis System API",
    description="API for uploading videos and analysing human pose using MediaPipe and ArangoDB.",
    version="1.0.0"
)

from starlette.middleware.sessions import SessionMiddleware

# CORS (Allow all for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session Middleware (Required for Google OAuth)
# Ensure SECRET_KEY is set in .env
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "CHANGE_THIS_IN_PRODUCTION_SECRET"))

# Include Routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["Dashboard"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(video.router, prefix="/api/v1/video", tags=["Video"])
app.include_router(reference.router, prefix="/api/v1/reference", tags=["Reference"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the Pose Analysis System API"}

if __name__ == "__main__":
    import uvicorn
    # Run with: python main.py
    # or uvicorn main:app --reload
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
#./.venv/bin/python main.py