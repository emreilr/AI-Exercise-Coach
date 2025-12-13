
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import Routers
from app.routers import video

app = FastAPI(
    title="Pose Analysis System API",
    description="API for uploading videos and analysing human pose using MediaPipe and ArangoDB.",
    version="1.0.0"
)

# CORS Configuration
# Allow all origins for development/testing ease, customize for production.
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(video.router, prefix="/api/v1/video", tags=["Video"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the Pose Analysis System API"}

if __name__ == "__main__":
    import uvicorn
    # Run with: python main.py
    # or uvicorn main:app --reload
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
