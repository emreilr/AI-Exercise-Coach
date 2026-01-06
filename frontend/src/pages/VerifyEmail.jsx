
import React, { useState } from 'react';
import client from '../api/client';
import { useNavigate, useLocation, Link } from 'react-router-dom';

const VerifyEmail = () => {
    const location = useLocation();
    const navigate = useNavigate();

    // Get email from state passed via navigation, or empty
    const [email, setEmail] = useState(location.state?.email || '');
    const [code, setCode] = useState('');
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setSuccess('');

        try {
            const formData = new FormData();
            formData.append('email', email);
            formData.append('code', code);

            await client.post('/auth/verify-email', formData);

            setSuccess("Email successfully verified! Redirecting to login...");
            setTimeout(() => {
                navigate('/login');
            }, 2000);

        } catch (err) {
            setError(err.response?.data?.detail || "Verification failed");
        }
    };

    return (
        <div style={{ padding: '20px', maxWidth: '400px', margin: '40px auto', border: '1px solid #ddd', borderRadius: '8px' }}>
            <h2 style={{ textAlign: 'center' }}>Verify Email</h2>
            <p style={{ textAlign: 'center', marginBottom: '20px' }}>Enter the code sent to your email.</p>

            {error && <div style={{ color: 'red', marginBottom: '10px', textAlign: 'center' }}>{error}</div>}
            {success && <div style={{ color: 'green', marginBottom: '10px', textAlign: 'center' }}>{success}</div>}

            <form onSubmit={handleSubmit}>
                <div style={{ marginBottom: '15px' }}>
                    <label style={{ display: 'block', marginBottom: '5px' }}>Email</label>
                    <input
                        type="email"
                        value={email}
                        onChange={e => setEmail(e.target.value)}
                        required
                        style={{ width: '100%', padding: '8px' }}
                    />
                </div>
                <div style={{ marginBottom: '15px' }}>
                    <label style={{ display: 'block', marginBottom: '5px' }}>Verification Code</label>
                    <input
                        type="text"
                        value={code}
                        onChange={e => setCode(e.target.value)}
                        required
                        placeholder="123456"
                        maxLength={6}
                        style={{ width: '100%', padding: '8px', letterSpacing: '2px', fontSize: '18px', textAlign: 'center' }}
                    />
                </div>
                <button type="submit" style={{ width: '100%', padding: '10px', backgroundColor: '#007bff', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                    Verify
                </button>
            </form>

            <div style={{ marginTop: '15px', textAlign: 'center' }}>
                <Link to="/login" style={{ fontSize: '14px' }}>Back to Login</Link>
            </div>
        </div>
    );
};

export default VerifyEmail;
