
import React, { useState, useEffect } from 'react';
import client from '../api/client';
import { useAuth } from '../context/AuthContext';
import { Link } from 'react-router-dom';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const AdminDashboard = () => {
    const { logout } = useAuth();
    const [activeTab, setActiveTab] = useState('exercises');

    // Data List
    const [exercises, setExercises] = useState([]);

    // Exercise State
    const [exerciseName, setExerciseName] = useState('');
    const [exerciseDesc, setExerciseDesc] = useState('');

    // Reference State
    const [refExerciseName, setRefExerciseName] = useState('');
    const [refFile, setRefFile] = useState(null);

    // Train State
    const [trainExerciseName, setTrainExerciseName] = useState('');
    const [activeTrainingExercise, setActiveTrainingExercise] = useState(null);
    const [trainingStatus, setTrainingStatus] = useState(null);

    // Developer State
    const [devUsername, setDevUsername] = useState('');
    const [devPassword, setDevPassword] = useState('');
    const [devFullname, setDevFullname] = useState('');
    const [batchFile, setBatchFile] = useState(null);

    // Benchmark State
    const [benchmarkResult, setBenchmarkResult] = useState(null);
    const [benchmarking, setBenchmarking] = useState(false);

    // Activity State
    const [activityReport, setActivityReport] = useState([]);
    const [loadingActivity, setLoadingActivity] = useState(false);

    // Control State (Developers & Logs)
    const [developers, setDevelopers] = useState([]);
    const [logs, setLogs] = useState([]);
    const [loadingControl, setLoadingControl] = useState(false);

    // Fetch Exercises
    const fetchExercises = async () => {
        try {
            const res = await client.get('/admin/exercises');
            setExercises(res.data);
        } catch (err) {
            console.error("Error fetching exercises:", err);
            alert("Error fetching exercises: " + (err.response?.data?.detail || err.message));
        }
    };

    // Initial Fetch
    useEffect(() => {
        fetchExercises();
    }, []);

    // Polling Effect
    useEffect(() => {
        let interval;
        if (activeTrainingExercise) {
            console.log("Starting polling for:", activeTrainingExercise);
            interval = setInterval(async () => {
                try {
                    const url = `/admin/train/status/${activeTrainingExercise}`;
                    const res = await client.get(url);
                    console.log("Poll response:", res.data);

                    setTrainingStatus(res.data);

                    if (res.data.status === 'completed' || res.data.status === 'failed') {
                        console.log("Training finished:", res.data.status);
                        clearInterval(interval);
                        setActiveTrainingExercise(null);
                        // No alert here, let the UI show the final status
                    }
                } catch (err) {
                    console.error("Polling error", err);
                }
            }, 1000);
        }
        return () => {
            if (interval) clearInterval(interval);
        };
    }, [activeTrainingExercise]);

    // --- Handlers ---

    const handleCreateExercise = async (e) => {
        e.preventDefault();
        try {
            const formData = new FormData();
            formData.append('name', exerciseName);
            formData.append('description', exerciseDesc);
            await client.post('/admin/exercise', formData);
            alert("Exercise Created!");
            setExerciseName('');
            setExerciseDesc('');
            fetchExercises(); // Refresh exercise list
        } catch (err) {
            alert("Error: " + (err.response?.data?.detail || err.message));
        }
    };

    const handleUploadReference = async (e) => {
        e.preventDefault();
        if (!refFile || !refExerciseName) {
            alert("Please select an exercise and a file.");
            return;
        }

        const selectedExercise = exercises.find(ex => ex.name === refExerciseName);
        if (!selectedExercise) {
            alert("Selected exercise not found.");
            return;
        }

        const formData = new FormData();
        formData.append('file', refFile);
        formData.append('exercise_name', refExerciseName);

        try {
            await client.post('/reference/upload', formData);
            alert("Reference video uploaded!");
            setRefExerciseName('');
            setRefFile(null);
            e.target.reset();
        } catch (err) {
            alert("Error: " + (err.response?.data?.detail || err.message));
        }
    };

    const handleTriggerTraining = async () => {
        if (!trainExerciseName) {
            alert("Please select an exercise to train.");
            return;
        }

        const selectedExercise = exercises.find(ex => ex.name === trainExerciseName);
        if (!selectedExercise) {
            alert("Selected exercise not found.");
            return;
        }

        try {
            const formData = new FormData();
            formData.append('exercise_name', trainExerciseName);
            await client.post('/admin/train', formData);

            // Start Polling
            setActiveTrainingExercise(trainExerciseName);
            // Initialize with safe defaults to prevent render issues
            setTrainingStatus({
                status: 'starting',
                message: 'Initiating...',
                progress: 0,
                epoch: 0,
                total_epochs: 25,
                loss: 0
            });

        } catch (err) {
            const detail = err.response?.data?.detail;
            const message = typeof detail === 'object' ? JSON.stringify(detail) : (detail || err.message);
            alert("Error: " + message);
        }
    };

    const handleCreateDeveloper = async (e) => {
        e.preventDefault();
        try {
            const formData = new FormData();
            formData.append('username', devUsername);
            formData.append('password', devPassword);
            formData.append('fullname', devFullname);
            await client.post('/auth/admin/create-developer', formData);
            alert("Developer account created successfully!");
            setDevUsername('');
            setDevPassword('');
            setDevFullname('');
        } catch (err) {
            alert("Error: " + (err.response?.data?.detail || err.message));
        }
    };

    const handleBatchCreateDevelopers = async (e) => {
        e.preventDefault();
        if (!batchFile) {
            alert("Please select a CSV file.");
            return;
        }

        const formData = new FormData();
        formData.append('file', batchFile);

        try {
            const res = await client.post('/auth/admin/batch-create-developers', formData);
            alert(`Batch Processed: ${res.data.message}`);
            if (res.data.errors && res.data.errors.length > 0) {
                console.warn("Batch errors:", res.data.errors);
                alert("Some rows failed. Check console for details.");
            }
            setBatchFile(null);
        } catch (err) {
            alert("Error: " + (err.response?.data?.detail || err.message));
        }
    };

    const handleRunBenchmark = async () => {
        setBenchmarking(true);
        try {
            const res = await client.get('/admin/benchmark');
            setBenchmarkResult(res.data);
        } catch (err) {
            alert("Benchmark failed.");
        } finally {
            setBenchmarking(false);
        }
    };

    const handleFetchActivity = async () => {
        setLoadingActivity(true);
        try {
            const res = await client.get('/admin/user-activity');
            setActivityReport(res.data);
        } catch (err) {
            console.error(err);
            alert("Failed to load activity report.");
        } finally {
            setLoadingActivity(false);
        }
    };

    const handleFetchControlData = async () => {
        setLoadingControl(true);
        try {
            const devRes = await client.get('/admin/developers');
            const logRes = await client.get('/admin/audit-logs');
            setDevelopers(devRes.data);
            setLogs(logRes.data);
        } catch (err) {
            console.error(err);
            alert("Failed to load system data.");
        } finally {
            setLoadingControl(false);
        }
    };

    // Auto load activity when tab is selected
    useEffect(() => {
        if (activeTab === 'activity') {
            handleFetchActivity();
        }
        if (activeTab === 'control') {
            handleFetchControlData();
        }
    }, [activeTab]);

    const renderTab = () => {
        const cardStyle = {
            border: '1px solid #ddd',
            borderRadius: '8px',
            padding: '20px',
            marginBottom: '20px',
            backgroundColor: '#fff',
            boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
        };

        const cardBodyStyle = {
            marginTop: '15px',
            paddingTop: '15px',
            borderTop: '1px solid #eee'
        };

        const inputStyle = {
            display: 'block', margin: '10px 0', padding: '10px', width: '100%', borderRadius: '4px', border: '1px solid #ccc', boxSizing: 'border-box'
        };
        const buttonStyle = {
            padding: '10px 20px', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', marginTop: '10px'
        };

        return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {activeTab === 'exercises' && (
                    <div style={cardStyle}>
                        <h3>Create Exercise</h3>
                        <form onSubmit={handleCreateExercise} style={cardBodyStyle}>
                            <input
                                placeholder="Exercise Name"
                                value={exerciseName}
                                onChange={e => setExerciseName(e.target.value)}
                                required
                                style={inputStyle}
                            />
                            <textarea
                                placeholder="Description"
                                value={exerciseDesc}
                                onChange={e => setExerciseDesc(e.target.value)}
                                style={{ ...inputStyle, minHeight: '80px' }}
                            />
                            <button type="submit" style={{ ...buttonStyle, backgroundColor: '#007bff' }}>Create</button>
                        </form>
                    </div>
                )}

                {activeTab === 'reference' && (
                    <>
                        <div style={cardStyle}>
                            <h3>Upload Reference Video</h3>
                            <form onSubmit={handleUploadReference} style={cardBodyStyle}>
                                <select
                                    value={refExerciseName}
                                    onChange={e => setRefExerciseName(e.target.value)}
                                    required
                                    style={inputStyle}
                                >
                                    <option value="" disabled>Select Exercise to Upload Video</option>
                                    {exercises.map(ex => (
                                        <option key={ex._key || ex.id} value={ex.name}>{ex.name}</option>
                                    ))}
                                </select>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                    <label style={{ cursor: 'pointer', backgroundColor: '#e9ecef', padding: '10px', borderRadius: '4px', flex: 1, textAlign: 'center' }}>
                                        {refFile ? refFile.name : "Choose Video File"}
                                        <input
                                            type="file"
                                            accept="video/*"
                                            onChange={e => setRefFile(e.target.files[0])}
                                            required
                                            style={{ display: 'none' }}
                                        />
                                    </label>
                                </div>
                                <button type="submit" style={{ ...buttonStyle, backgroundColor: '#28a745' }}>Upload Reference</button>
                            </form>
                        </div>

                        <div style={cardStyle}>
                            <h3>Trigger Training</h3>
                            <p style={{ marginBottom: '15px' }}>After uploading references, trigger training to update model and embeddings.</p>
                            <div style={cardBodyStyle}>
                                <select
                                    value={trainExerciseName}
                                    onChange={e => setTrainExerciseName(e.target.value)}
                                    style={inputStyle}
                                    disabled={!!activeTrainingExercise}
                                >
                                    <option value="">Select Exercise to Train</option>
                                    {exercises.map(ex => (
                                        <option key={ex._key || ex.id} value={ex.name}>{ex.name}</option>
                                    ))}
                                </select>
                                <button
                                    onClick={handleTriggerTraining}
                                    disabled={!!activeTrainingExercise}
                                    style={{ ...buttonStyle, backgroundColor: activeTrainingExercise ? '#6c757d' : '#ffc107', color: 'black' }}
                                >
                                    {activeTrainingExercise ? "Training in Progress..." : "Start Training"}
                                </button>
                            </div>

                            {/* Training Status Visualization */}
                            {trainingStatus && (
                                <div style={{ marginTop: '20px', padding: '15px', backgroundColor: '#f8f9fa', borderRadius: '5px', border: '1px solid #e9ecef' }}>
                                    <h4 style={{ margin: '0 0 10px 0' }}>Training Status: <span style={{ color: trainingStatus.status === 'failed' ? 'red' : 'green' }}>{trainingStatus.status.toUpperCase()}</span></h4>
                                    <p style={{ margin: '5px 0', fontSize: '14px' }}>{trainingStatus.message}</p>

                                    {/* Progress Bar */}
                                    <div style={{ width: '100%', height: '20px', backgroundColor: '#e9ecef', borderRadius: '10px', overflow: 'hidden', margin: '10px 0' }}>
                                        <div style={{
                                            width: `${trainingStatus.progress}%`,
                                            height: '100%',
                                            backgroundColor: trainingStatus.status === 'failed' ? '#dc3545' : '#28a745',
                                            transition: 'width 0.5s ease-in-out'
                                        }}></div>
                                    </div>

                                    {/* Stats */}
                                    <div style={{ display: 'flex', gap: '20px', fontSize: '14px', color: '#666' }}>
                                        <span>Epoch: {trainingStatus.epoch} / {trainingStatus.total_epochs}</span>
                                        <span>Loss: {trainingStatus.loss ? trainingStatus.loss.toFixed(4) : 'N/A'}</span>
                                    </div>
                                </div>
                            )}
                        </div>
                    </>
                )}

                {activeTab === 'developers' && (
                    <div style={cardStyle}>
                        <h3>Create New Developer</h3>
                        <p style={{ marginBottom: '10px', color: '#666' }}>Add another administrator to the system.</p>
                        <form onSubmit={handleCreateDeveloper} style={cardBodyStyle}>
                            <input
                                placeholder="Username"
                                value={devUsername}
                                onChange={e => setDevUsername(e.target.value)}
                                required
                                style={inputStyle}
                            />
                            <input
                                type="password"
                                placeholder="Password"
                                value={devPassword}
                                onChange={e => setDevPassword(e.target.value)}
                                required
                                style={inputStyle}
                            />
                            <input
                                placeholder="Full Name (Optional)"
                                value={devFullname}
                                onChange={e => setDevFullname(e.target.value)}
                                style={inputStyle}
                            />
                            <button type="submit" style={{ ...buttonStyle, backgroundColor: '#6f42c1' }}>Create Developer</button>
                        </form>

                        <div style={{ marginTop: '30px', paddingTop: '20px', borderTop: '1px solid #eee' }}>
                            <h4>Batch Import (CSV)</h4>
                            <p style={{ fontSize: '14px', color: '#666', marginBottom: '10px' }}>
                                Upload a CSV file with columns: <code>username, password, full_name</code>
                            </p>
                            <form onSubmit={handleBatchCreateDevelopers} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                <input
                                    type="file"
                                    accept=".csv"
                                    onChange={e => setBatchFile(e.target.files[0])}
                                    required
                                    style={{ padding: '5px' }}
                                />
                                <button type="submit" style={{ padding: '8px 15px', backgroundColor: '#17a2b8', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                                    Upload CSV
                                </button>
                            </form>
                        </div>
                    </div>
                )}

                {activeTab === 'activity' && (
                    <div style={cardStyle}>
                        <h3>User Daily Activity Report</h3>
                        <p style={{ marginBottom: '10px', color: '#666' }}>Shows how many times each user performed a specific exercise per day.</p>

                        <div style={cardBodyStyle}>
                            <button onClick={handleFetchActivity} style={{ ...buttonStyle, backgroundColor: '#17a2b8', marginBottom: '15px' }}>Refresh</button>

                            {loadingActivity ? <p>Loading report...</p> : (
                                <div style={{ overflowX: 'auto' }}>
                                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                                        <thead>
                                            <tr style={{ backgroundColor: '#f8f9fa', borderBottom: '2px solid #dee2e6' }}>
                                                <th style={{ padding: '12px' }}>Date</th>
                                                <th style={{ padding: '12px' }}>User</th>
                                                <th style={{ padding: '12px' }}>Exercise</th>
                                                <th style={{ padding: '12px' }}>Session Count</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {activityReport.length === 0 ? (
                                                <tr><td colSpan="4" style={{ padding: '15px', textAlign: 'center' }}>No activity found.</td></tr>
                                            ) : (
                                                activityReport.map((row, idx) => (
                                                    <tr key={idx} style={{ borderBottom: '1px solid #dee2e6' }}>
                                                        <td style={{ padding: '12px' }}>{row.date}</td>
                                                        <td style={{ padding: '12px' }}>{row.username}</td>
                                                        <td style={{ padding: '12px' }}>{row.exercise}</td>
                                                        <td style={{ padding: '12px', fontWeight: 'bold' }}>{row.count}</td>
                                                    </tr>
                                                ))
                                            )}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {activeTab === 'control' && (
                    <div style={cardStyle}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <h3>System Logs & Developers</h3>
                            <button onClick={handleFetchControlData} style={{ ...buttonStyle, backgroundColor: '#17a2b8', marginTop: 0 }}>Refresh Data</button>
                        </div>

                        {loadingControl ? <p>Loading data...</p> : (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '40px', marginTop: '20px' }}>

                                {/* Developers Table */}
                                <div>
                                    <h4 style={{ borderBottom: '2px solid #007bff', paddingBottom: '5px', display: 'inline-block' }}>System Developers</h4>
                                    <div style={{ overflowX: 'auto', marginTop: '10px' }}>
                                        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '14px' }}>
                                            <thead>
                                                <tr style={{ backgroundColor: '#e9ecef' }}>
                                                    <th style={{ padding: '8px' }}>Username</th>
                                                    <th style={{ padding: '8px' }}>Full Name</th>
                                                    <th style={{ padding: '8px' }}>Verified</th>
                                                    <th style={{ padding: '8px' }}>Created At</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {developers.map((dev, idx) => (
                                                    <tr key={idx} style={{ borderBottom: '1px solid #dee2e6' }}>
                                                        <td style={{ padding: '8px', fontWeight: 'bold' }}>{dev.username}</td>
                                                        <td style={{ padding: '8px' }}>{dev.full_name}</td>
                                                        <td style={{ padding: '8px' }}>{dev.is_verified ? 'Yes' : 'No'}</td>
                                                        <td style={{ padding: '8px' }}>{new Date(dev.created_at).toLocaleString()}</td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>

                                {/* Logs Table */}
                                <div>
                                    <h4 style={{ borderBottom: '2px solid #dc3545', paddingBottom: '5px', display: 'inline-block' }}>Trigger Audit Logs (Last 100)</h4>
                                    <div style={{ overflowX: 'auto', maxHeight: '400px', marginTop: '10px' }}>
                                        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                                            <thead>
                                                <tr style={{ backgroundColor: '#e9ecef', position: 'sticky', top: 0 }}>
                                                    <th style={{ padding: '8px' }}>Timestamp</th>
                                                    <th style={{ padding: '8px' }}>Action</th>
                                                    <th style={{ padding: '8px' }}>Details</th>
                                                    <th style={{ padding: '8px' }}>By</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {logs.map((log, idx) => (
                                                    <tr key={idx} style={{ borderBottom: '1px solid #f8f9fa', backgroundColor: idx % 2 === 0 ? '#fff' : '#fcfcfc' }}>
                                                        <td style={{ padding: '8px', whiteSpace: 'nowrap', color: '#666' }}>{new Date(log.timestamp).toLocaleString()}</td>
                                                        <td style={{ padding: '8px', fontWeight: 'bold', color: '#007bff' }}>{log.action}</td>
                                                        <td style={{ padding: '8px' }}>{log.details}</td>
                                                        <td style={{ padding: '8px', fontStyle: 'italic' }}>{log.performed_by}</td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>

                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'benchmark' && (
                    <div style={cardStyle}>
                        <h3>System Benchmark</h3>
                        <div style={cardBodyStyle}>
                            <button onClick={handleRunBenchmark} disabled={benchmarking} style={{ ...buttonStyle, backgroundColor: '#6c757d' }}>
                                {benchmarking ? "Running..." : "Run Benchmark"}
                            </button>
                            {benchmarkResult && (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '40px', marginTop: '30px' }}>

                                    {/* 1. Write Speed (Bar) */}
                                    <div style={{ height: '300px' }}>
                                        <h4 style={{ textAlign: 'center', marginBottom: '10px' }}>Write Speed (Lower is Better)</h4>
                                        <ResponsiveContainer width="100%" height="100%">
                                            <BarChart
                                                data={benchmarkResult.barData || []}
                                                margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
                                            >
                                                <CartesianGrid strokeDasharray="3 3" />
                                                <XAxis dataKey="metric" />
                                                <YAxis label={{ value: 'Time (s)', angle: -90, position: 'insideLeft' }} />
                                                <Tooltip />
                                                <Legend />
                                                <Bar dataKey="ArangoDB" fill="#8884d8" name="ArangoDB" />
                                                <Bar dataKey="OrientDB" fill="#82ca9d" name="OrientDB" />
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </div>

                                    {/* 2. Depth Traversal (Line) */}
                                    <div style={{ height: '300px' }}>
                                        <h4 style={{ textAlign: 'center', marginBottom: '10px' }}>Read Time vs Depth (Sequencing)</h4>
                                        <ResponsiveContainer width="100%" height="100%">
                                            <LineChart
                                                data={benchmarkResult.lineData || []}
                                                margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
                                            >
                                                <CartesianGrid strokeDasharray="3 3" />
                                                <XAxis dataKey="depth" label={{ value: 'Depth', position: 'insideBottom', offset: -5 }} />
                                                <YAxis label={{ value: 'Time (s)', angle: -90, position: 'insideLeft' }} />
                                                <Tooltip />
                                                <Legend />
                                                <Line type="monotone" dataKey="ArangoDB" stroke="#8884d8" activeDot={{ r: 8 }} strokeWidth={2} />
                                                <Line type="monotone" dataKey="OrientDB" stroke="#82ca9d" strokeWidth={2} />
                                            </LineChart>
                                        </ResponsiveContainer>
                                    </div>

                                    {/* 3. Latency Benchmark (Table) */}
                                    <div style={{ padding: '0 20px' }}>
                                        <div style={{ height: '300px' }}>
                                            <h4 style={{ textAlign: 'center', marginBottom: '10px' }}>Single Operation Latency (Lower is Better)</h4>
                                            <ResponsiveContainer width="100%" height="100%">
                                                <BarChart
                                                    data={benchmarkResult.latencyData || []}
                                                    margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
                                                >
                                                    <CartesianGrid strokeDasharray="3 3" />
                                                    <XAxis dataKey="metric" />
                                                    <YAxis label={{ value: 'Time (ms)', angle: -90, position: 'insideLeft' }} />
                                                    <Tooltip />
                                                    <Legend />
                                                    <Bar dataKey="ArangoDB" fill="#8884d8" name="ArangoDB (ms)" />
                                                    <Bar dataKey="OrientDB" fill="#82ca9d" name="OrientDB (ms)" />
                                                </BarChart>
                                            </ResponsiveContainer>
                                        </div>
                                    </div>

                                    {/* 4. Disk Usage (Table) */}
                                    <div style={{ padding: '0 20px' }}>
                                        <h4 style={{ textAlign: 'center', marginBottom: '10px' }}>Disk Usage (1000 Nodes Chain)</h4>
                                        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'center' }}>
                                            <thead>
                                                <tr style={{ backgroundColor: '#f8f9fa' }}>
                                                    <th style={{ padding: '10px', border: '1px solid #dee2e6' }}>Metric</th>
                                                    <th style={{ padding: '10px', border: '1px solid #dee2e6' }}>ArangoDB</th>
                                                    <th style={{ padding: '10px', border: '1px solid #dee2e6' }}>OrientDB</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {(benchmarkResult.diskData || []).map((row, idx) => (
                                                    <tr key={idx}>
                                                        <td style={{ padding: '10px', border: '1px solid #dee2e6' }}>{row.metric}</td>
                                                        <td style={{ padding: '10px', border: '1px solid #dee2e6' }}>{row.ArangoDB}</td>
                                                        <td style={{ padding: '10px', border: '1px solid #dee2e6' }}>{row.OrientDB}</td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>

                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        );
    };

    const getTabStyle = (tabName) => ({
        padding: '12px 20px',
        fontWeight: activeTab === tabName ? 'bold' : 'normal',
        border: 'none',
        backgroundColor: activeTab === tabName ? '#007bff' : 'transparent',
        color: activeTab === tabName ? 'white' : '#007bff',
        borderRadius: '5px',
        cursor: 'pointer',
        transition: 'all 0.2s',
        fontSize: '16px'
    });

    return (
        <div style={{ padding: '20px', maxWidth: '1000px', margin: '0 auto', fontFamily: 'Arial, sans-serif', backgroundColor: '#f4f6f8', minHeight: '100vh' }}>
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px', paddingBottom: '15px', borderBottom: '2px solid #e9ecef' }}>
                <h1 style={{ color: '#343a40', fontSize: '28px', margin: 0 }}>Admin Dashboard</h1>
                <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                    <Link to="/dashboard" style={{ textDecoration: 'none', color: '#007bff', fontWeight: 'bold' }}>To User View &rarr;</Link>
                    <button onClick={logout} style={{ padding: '8px 15px', backgroundColor: '#dc3545', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Logout</button>
                </div>
            </header>

            <div style={{ marginBottom: '25px', display: 'flex', gap: '10px', flexWrap: 'wrap', backgroundColor: '#fff', padding: '10px', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                <button onClick={() => setActiveTab('exercises')} style={getTabStyle('exercises')}>Exercises</button>
                <button onClick={() => setActiveTab('reference')} style={getTabStyle('reference')}>Reference & Training</button>
                <button onClick={() => setActiveTab('developers')} style={getTabStyle('developers')}>Manage Developers</button>
                <button onClick={() => setActiveTab('activity')} style={getTabStyle('activity')}>User Activity</button>
                <button onClick={() => setActiveTab('control')} style={getTabStyle('control')}>System Logs</button>
                <button onClick={() => setActiveTab('benchmark')} style={getTabStyle('benchmark')}>Benchmark</button>
            </div>

            {renderTab()}
        </div>
    );
};

export default AdminDashboard;
