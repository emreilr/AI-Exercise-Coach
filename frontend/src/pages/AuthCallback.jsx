
import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { jwtDecode } from "jwt-decode";

const AuthCallback = () => {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const { setUser } = useAuth(); // We might need to expose setUser or use a specific login method

    useEffect(() => {
        const token = searchParams.get('token');
        if (token) {
            try {
                // Store token
                localStorage.setItem('token', token);

                // Decode to get user info
                const decoded = jwtDecode(token);

                // Update Context (assuming standard context structure)
                // If setUser is not exposed, we might need to reload or dispatch an event
                // But usually we can just reload the page or navigate and let App.jsx init check pick it up

                // For smoother experience, let's try to reload the window to ensure AuthContext picks it up fresh
                // Or if we can update state without reload:
                // setUser({ ...decoded, token });

                // Simple approach: Redirect to dashboard, AuthContext init logic in App.jsx/Context will read localStorage?
                // Looking at AuthContext.jsx (via memory), it usually checks localStorage on mount.
                // Since we are already mounted, we might need to trigger a re-check or reload.

                window.location.href = '/dashboard';

            } catch (err) {
                console.error("Token decoding failed", err);
                navigate('/login?error=auth_failed');
            }
        } else {
            navigate('/login?error=no_token');
        }
    }, [searchParams, navigate]);

    return (
        <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100vh',
            fontSize: '1.2rem',
            color: '#666'
        }}>
            Authenticating...
        </div>
    );
};

export default AuthCallback;
