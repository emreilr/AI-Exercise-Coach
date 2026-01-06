
import React, { useEffect, useState } from 'react';
import client from '../api/client';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const Dashboard = () => {
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(true);
    const { user, logout } = useAuth();
    const navigate = useNavigate();

    // Profile State
    const [showProfile, setShowProfile] = useState(false);
    const [profile, setProfile] = useState({
        full_name: '',
        birth_date: '',
        height: '',
        password: ''
    });

    useEffect(() => {
        const fetchHistory = async () => {
            try {
                const res = await client.get('/user/history');
                setHistory(res.data);
            } catch (err) {
                console.error("Failed to fetch history", err);
            } finally {
                setLoading(false);
            }
        };

        const fetchProfile = async () => {
            try {
                const res = await client.get('/auth/user/me');
                setProfile(prev => ({
                    ...prev,
                    full_name: res.data.full_name || '',
                    birth_date: res.data.birth_date || '',
                    height: res.data.height || '',
                    password: '' // Don't prefill password
                }));
            } catch (err) {
                console.error("Failed to fetch profile", err);
            }
        };

        fetchHistory();
        fetchProfile();
    }, []);

    const handleUpdateProfile = async (e) => {
        e.preventDefault();
        try {
            const formData = new FormData();
            if (profile.full_name) formData.append('fullname', profile.full_name);
            if (profile.birth_date) formData.append('birth_date', profile.birth_date);
            if (profile.height) formData.append('height', profile.height);
            if (profile.password) formData.append('password', profile.password);

            await client.patch('/auth/user/me', formData);
            alert("Profile updated successfully!");
            setProfile(prev => ({ ...prev, password: '' })); // Clear password field
        } catch (err) {
            alert("Error updating profile: " + (err.response?.data?.detail || err.message));
        }
    };

    const handleExport = async (format) => {
        try {
            const response = await client.get(`/user/history/export?format=${format}`, {
                responseType: 'blob',
            });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `history.${format}`);
            document.body.appendChild(link);
            link.click();
        } catch (error) {
            console.error("Export failed", error);
        }
    };

    // Stats State
    const [stats, setStats] = useState(null);
    const [showStats, setShowStats] = useState(false);
    const [statsLoading, setStatsLoading] = useState(false);

    const handleViewStats = async (exerciseId) => {
        setStatsLoading(true);
        setShowStats(true);
        setStats(null); // Clear previous
        try {
            const res = await client.get(`/user/stats/${exerciseId}`);
            setStats(res.data);
        } catch (err) {
            console.error("Failed to fetch stats", err);
            setShowStats(false);
            alert("Could not load statistics.");
        } finally {
            setStatsLoading(false);
        }
    };

    if (loading) return <div>Loading history...</div>;

    return (
        <div className="card wide">
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h1>Patient Dashboard</h1>
                <button onClick={logout} style={{ width: 'auto', backgroundColor: '#dc3545' }}>Logout</button>
            </header>

            <div style={{ marginBottom: '30px', textAlign: 'center' }}>
                <Link to="/upload">
                    <button style={{ maxWidth: '300px' }}>Start New Session (Upload Video)</button>
                </Link>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <h2>Session History</h2>
                <div>
                    <button onClick={() => setShowProfile(!showProfile)} style={{ width: 'auto', marginRight: '10px', backgroundColor: showProfile ? '#6c757d' : '#007bff' }} className="secondary">
                        {showProfile ? "Hide Profile" : "Edit Profile"}
                    </button>
                    <button onClick={() => handleExport('csv')} style={{ width: 'auto', marginRight: '10px', fontSize: '14px' }} className="secondary">Export CSV</button>
                    <button onClick={() => handleExport('json')} style={{ width: 'auto', fontSize: '14px' }} className="secondary">Export JSON</button>
                </div>
            </div>

            {/* Stats Modal / Overlay */}
            {showStats && (
                <div style={{
                    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                    backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000
                }}>
                    <div style={{ backgroundColor: 'white', padding: '20px', borderRadius: '8px', minWidth: '300px', maxWidth: '500px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                            <h3 style={{ margin: 0 }}>Exercise Statistics</h3>
                            <button onClick={() => setShowStats(false)} style={{ background: 'none', border: 'none', fontSize: '20px', cursor: 'pointer' }}>&times;</button>
                        </div>

                        {statsLoading ? <p>Loading analysis...</p> : (
                            stats ? (
                                <div>
                                    <p><strong>Your Average Score:</strong> {stats.personal_avg.toFixed(1)}%</p>
                                    <p><strong>Global Average:</strong> {stats.global_avg.toFixed(1)}%</p>
                                    <p><strong>Total Participants:</strong> {stats.total_participants}</p>
                                    <hr style={{ margin: '15px 0', borderTop: '1px solid #eee' }} />
                                    <p style={{ fontSize: '0.9em', color: '#666' }}>
                                        {stats.personal_avg > stats.global_avg
                                            ? "Great job! You are above the average."
                                            : "Keep practicing to beat the global average!"}
                                    </p>
                                </div>
                            ) : <p>No data available.</p>
                        )}
                        <button onClick={() => setShowStats(false)} style={{ marginTop: '15px', width: '100%' }}>Close</button>
                    </div>
                </div>
            )}

            {showProfile && (
                <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #ddd', borderRadius: '8px', backgroundColor: '#f9f9f9' }}>
                    <h3>Edit Profile</h3>
                    <form onSubmit={handleUpdateProfile} style={{ display: 'grid', gap: '10px', maxWidth: '400px' }}>
                        <div>
                            <label style={{ display: 'block', marginBottom: '5px' }}>Full Name</label>
                            <input
                                value={profile.full_name}
                                onChange={e => setProfile({ ...profile, full_name: e.target.value })}
                                style={{ width: '100%', padding: '8px' }}
                            />
                        </div>
                        <div>
                            <label style={{ display: 'block', marginBottom: '5px' }}>Birth Date</label>
                            <input
                                type="date"
                                value={profile.birth_date}
                                onChange={e => setProfile({ ...profile, birth_date: e.target.value })}
                                style={{ width: '100%', padding: '8px' }}
                            />
                        </div>
                        <div>
                            <label style={{ display: 'block', marginBottom: '5px' }}>Height (cm)</label>
                            <input
                                type="number"
                                value={profile.height}
                                onChange={e => setProfile({ ...profile, height: e.target.value })}
                                style={{ width: '100%', padding: '8px' }}
                            />
                        </div>
                        <div>
                            <label style={{ display: 'block', marginBottom: '5px' }}>New Password (leave blank to keep current)</label>
                            <input
                                type="password"
                                value={profile.password}
                                onChange={e => setProfile({ ...profile, password: e.target.value })}
                                style={{ width: '100%', padding: '8px' }}
                            />
                        </div>
                        <button type="submit" style={{ backgroundColor: '#28a745', color: 'white', padding: '10px', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                            Save Changes
                        </button>
                    </form>
                </div>
            )}

            {loading ? <p>Loading history...</p> : (
                <div style={{ overflowX: 'auto' }}>
                    <table>
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Exercise</th>
                                <th>Score</th>
                                <th>Feedback</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {history.length === 0 ? (
                                <tr>
                                    <td colSpan="5" style={{ textAlign: 'center' }}>No sessions found.</td>
                                </tr>
                            ) : (
                                history.map(session => (
                                    <tr key={session.session_id}>
                                        <td>{new Date(session.timestamp).toLocaleString()}</td>
                                        <td>
                                            {session.exercise_name}
                                            {session.exercise_id && (
                                                <button
                                                    onClick={() => handleViewStats(session.exercise_id)}
                                                    style={{ marginLeft: '10px', padding: '2px 8px', fontSize: '0.8em', backgroundColor: '#17a2b8' }}
                                                >
                                                    View Stats
                                                </button>
                                            )}
                                        </td>
                                        <td>{session.score !== undefined ? session.score.toFixed(2) : 'N/A'}</td>
                                        <td>{session.feedback || '-'}</td>
                                        <td>
                                            <Link to={`/session/${session.session_id}`}>Details</Link>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};

export default Dashboard;

