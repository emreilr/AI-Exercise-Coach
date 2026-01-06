# AI-Powered Exercise Analysis System

## Overview

This project is an advanced **AI-driven exercise analysis platform** designed to evaluate user exercise performance automatically. By leveraging computer vision and deep learning, the system analyzes video uploads, extracts human skeletal pose data, and compares it against professional reference standards to provide accurate scoring and feedback.

The core technology relies on **Spatial-Temporal Graph Convolutional Networks (ST-GCN)** and **SimCLR** (Contrastive Learning) to generate robust motion embeddings, enabling precise action recognition and quality assessment using **Dynamic Time Warping (DTW)**.

## Key Features

-   **Video Ingestion**: Secure upload and processing of user exercise videos.
-   **Pose Estimation**: Real-time skeletal tracking using **MediaPipe**.
-   **Action Recognition**: Utilization of **ST-GCN** to understand complex human movements.
-   **Performance Scoring**: Comparison of user movements with expert references using **DTW** for temporal alignment and similarity scoring.
-   **Dual-Database Architecture**: Stores graph-based skeletal data in **ArangoDB** and syncs with **OrientDB** for robust data management.
-   **User Dashboard**: Comprehensive analytics, session history, and progress tracking.
-   **Authentication**: Secure user login and management, including Google OAuth support.

## Technology Stack

### Backend & AI
-   **Python**: Core programming language.
-   **FastAPI**: High-performance web framework for the API.
-   **PyTorch**: Deep learning framework for the ST-GCN model.
-   **MediaPipe**: Framework for building multimodal applied ML pipelines (Pose Estimation).
-   **OpenCV**: Computer vision library for video processing.
-   **FastAPI Mail**: For email notifications and verification.

### Database
-   **ArangoDB**: Primary multi-model graph database for storing user data, video metadata, and skeletal graphs.
-   **OrientDB**: Secondary graph database for data redundancy and synchronization.

### Frontend
-   **React**: JavaScript library for building the user interface.
-   **Vite**: Next Generation Frontend Tooling.
-   **TailwindCSS**: Utility-first CSS framework for styling.

## How It Works

1.  **Upload**: A user uploads a video of themselves performing an exercise (e.g., Pushups, Squats).
2.  **Processing**: The backend processes the video frame-by-frame, extracting 33-point skeletal landmarks.
3.  **Embedding**: These landmarks are fed into the trained **ST-GCN** model to generate high-dimensional motion embeddings.
4.  **Evaluation**: The system retrieves the "Golden Reference" for that specific exercise and employs **DTW** to calculate a similarity score (0-100).
5.  **Feedback**: The user receives an immediate score and qualitative feedback (e.g., "Excellent form", "Watch your alignment") on their dashboard.

## Setup

### Prerequisites
-   **Python 3.10**: This project relies on Python 3.10.
-   **Node.js**: Required for the frontend.
-   **Databases**: Ensure **ArangoDB** and **OrientDB** are running.

### Installation & Running

1.  **Backend**:
    Install dependencies and run the server using the virtual environment python:
    ```bash
    # Install dependencies
    ./.venv/bin/pip install -r requirements.txt

    # Run the Backend
    ./.venv/bin/python main.py
    ```

2.  **Frontend**:
    Navigate to the frontend directory and start the development server:
    ```bash
    cd frontend
    npm install
    npm run dev
    ```

License
This project is open-source and available under the MIT License.
