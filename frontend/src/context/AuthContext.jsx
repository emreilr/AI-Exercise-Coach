
import React, { createContext, useState, useEffect, useContext } from 'react';
import { jwtDecode } from "jwt-decode";
import client from '../api/client';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // Check for token on mount
        const token = localStorage.getItem('token');
        if (token) {
            try {
                const decoded = jwtDecode(token);
                // Basic check if expired
                if (decoded.exp * 1000 < Date.now()) {
                    localStorage.removeItem('token');
                    setUser(null);
                } else {
                    setUser({ ...decoded, token });
                }
            } catch (e) {
                localStorage.removeItem('token');
                setUser(null);
            }
        }
        setLoading(false);
    }, []);

    const login = async (username, password) => {
        // OAuth2PasswordRequestForm expects x-www-form-urlencoded
        const params = new URLSearchParams();
        params.append('username', username);
        params.append('password', password);

        try {
            const response = await client.post('/auth/login', params, {
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
            });
            const { access_token } = response.data;

            localStorage.setItem('token', access_token);
            const decoded = jwtDecode(access_token);
            setUser({ ...decoded, token: access_token });
            return { success: true, user: decoded };
        } catch (error) {
            return {
                success: false,
                message: error.response?.data?.detail || 'Login failed'
            };
        }
    };

    const logout = () => {
        localStorage.removeItem('token');
        setUser(null);
    };

    const signup = async (data) => {
        const formData = new FormData();
        for (const key in data) {
            formData.append(key, data[key]);
        }
        try {
            const response = await client.post('/auth/signup', formData);
            return { success: true, ...response.data };
        } catch (error) {
            return { success: false, message: error.response?.data?.detail || 'Signup failed' };
        }
    };

    return (
        <AuthContext.Provider value={{ user, login, logout, signup, loading }}>
            {!loading && children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);
