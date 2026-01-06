
import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import client from '../api/client';

const SessionResult = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        const fetchResult = async () => {
            try {
                const res = await client.get(`/session/${id}/result`);
                setResult(res.data);
            } catch (err) {
                setError("Failed to load result. It might not be ready yet.");
            } finally {
                setLoading(false);
            }
        };
        fetchResult();
    }, [id]);

    if (loading) return <div>Loading result...</div>;
    if (error) return <div style={{ color: 'red' }}>{error} <br /><Link to="/dashboard">Back to Dashboard</Link></div>;

    return (
        <div className="card">
            <h2>Session Result</h2>
            <div style={{ marginBottom: '20px' }}>
                <p><strong>Date:</strong> {new Date(result.timestamp).toLocaleString()}</p>
                <p><strong>Exercise:</strong> {result.exercise_name}</p>
                <p><strong>Score:</strong> <span style={{ fontSize: '1.2em', fontWeight: 'bold' }}>{result.score.toFixed(2)}</span> / 100</p>
            </div>

            <div style={{ marginBottom: '20px' }}>
                <h3>Feedback</h3>
                <p>{result.feedback}</p>
            </div>

            <div style={{ marginTop: '20px', fontSize: '14px', color: '#666' }}>
                Video ID: {result.video_id} <br />
                Session ID: {result.session_id}
            </div>

            <button onClick={() => navigate('/dashboard')} style={{ marginTop: '20px' }}>Back to Dashboard</button>
        </div>
    );
};

export default SessionResult;
