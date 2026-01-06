
import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate, Link } from 'react-router-dom';

const Signup = () => {
    const [formData, setFormData] = useState({
        username: '',
        email: '',
        password: '',
        fullname: '',
        birth_date: '',
        height: ''
    });
    const [error, setError] = useState('');
    const { signup } = useAuth();
    const navigate = useNavigate();

    const handleChange = (e) => {
        setFormData({
            ...formData,
            [e.target.name]: e.target.value
        });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        const res = await signup(formData);
        if (res.success) {
            if (res.require_verification) {
                navigate('/verify-email', { state: { email: formData.email } });
            } else {
                alert("Account created! Please login.");
                navigate('/login');
            }
        } else {
            setError(res.message);
        }
    };

    return (
        <div className="card">
            <h2>Sign Up</h2>
            {error && <p style={{ color: 'red' }}>{error}</p>}
            <form onSubmit={handleSubmit}>
                <div style={{ marginBottom: '10px' }}>
                    <label>Username:</label>
                    <input name="username" value={formData.username} onChange={handleChange} required />
                </div>
                <div style={{ marginBottom: '10px' }}>
                    <label>Email:</label>
                    <input type="email" name="email" value={formData.email} onChange={handleChange} required />
                </div>
                <div style={{ marginBottom: '10px' }}>
                    <label>Password:</label>
                    <input type="password" name="password" value={formData.password} onChange={handleChange} required />
                </div>
                <div style={{ marginBottom: '10px' }}>
                    <label>Full Name:</label>
                    <input name="fullname" value={formData.fullname} onChange={handleChange} required />
                </div>
                {/* Optional fields if needed */}
                <button type="submit">Sign Up</button>
            </form>
            <p style={{ textAlign: 'center', marginTop: '15px' }}>
                Already have an account? <Link to="/login">Login</Link>
            </p>
            <div style={{ marginTop: '20px', textAlign: 'center' }}>
                <a href="http://localhost:8000/api/v1/auth/google/login">
                    <button className="secondary" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto' }}>
                        <svg width="20px" height="20px" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" style={{ marginRight: '10px' }}>
                            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
                            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                            <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                        </svg>
                        Sign up with Google
                    </button>
                </a>
            </div>
        </div>
    );
};

export default Signup;
