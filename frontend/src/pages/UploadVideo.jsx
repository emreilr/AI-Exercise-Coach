

import React, { useState, useEffect } from 'react';
import client from '../api/client';
import { useNavigate } from 'react-router-dom';

const UploadVideo = () => {
    const [file, setFile] = useState(null);
    const [exercises, setExercises] = useState([]);
    const [selectedExercise, setSelectedExercise] = useState('');
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState('');

    const navigate = useNavigate();

    useEffect(() => {
        const fetchExercises = async () => {
            try {
                const res = await client.get('/admin/exercises');
                setExercises(res.data);
                if (res.data.length > 0) {
                    setSelectedExercise(res.data[0].name);
                }
            } catch (err) {
                console.error("Failed to load exercises", err);
            }
        };
        fetchExercises();
    }, []);

    const handleFileChange = (e) => {
        setFile(e.target.files[0]);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!file || !selectedExercise) {
            setError("Please select a file and an exercise");
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('exercise_name', selectedExercise);
        // user_id is handled by backend from token? 
        // Wait, video.py expects user_id form field.
        // It should extract from token! But video.py takes user_id: str = Form(...).
        // Let's check video.py again. 
        // If video.py requires user_id Form param, we need to send it.
        // AuthContext has user info.
        // Let's grab user from context.

        setUploading(true);
        setError('');

        try {
            await client.post('/video/upload', formData);
            alert("Video uploaded! Processing started. Check dashboard for results shortly.");
            navigate('/dashboard');
        } catch (err) {
            console.error(err);
            const detail = err.response?.data?.detail;
            const message = typeof detail === 'object' ? JSON.stringify(detail) : (detail || err.message);
            setError("Upload failed: " + message);
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="card">
            <h2>Upload Video</h2>
            {error && <p style={{ color: 'red' }}>{error}</p>}

            <form onSubmit={handleSubmit}>
                <div style={{ marginBottom: '20px' }}>
                    <label>Select Exercise:</label>
                    <select
                        value={selectedExercise}
                        onChange={(e) => setSelectedExercise(e.target.value)}
                        required
                    >
                        <option value="" disabled>-- Select --</option>
                        {exercises.map(ex => (
                            <option key={ex.id} value={ex.name}>{ex.name}</option>
                        ))}
                    </select>
                </div>

                <div style={{ marginBottom: '20px' }}>
                    <label>Video File:</label>
                    <input type="file" accept="video/*" onChange={handleFileChange} required />
                </div>

                <div style={{ display: 'flex', gap: '10px' }}>
                    <button type="button" className="secondary" onClick={() => navigate('/dashboard')}>Cancel</button>
                    <button type="submit" disabled={uploading}>
                        {uploading ? "Uploading..." : "Upload & Analyze"}
                    </button>
                </div>
            </form>
        </div>
    );
};

export default UploadVideo;
