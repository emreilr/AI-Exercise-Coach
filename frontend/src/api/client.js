
import axios from 'axios';

const client = axios.create({
    baseURL: '/api/v1',
});

// Interceptor to add JWT token to requests
client.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token');
        if (token) {
            config.headers['Authorization'] = `Bearer ${token}`;
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// Interceptor to handle 401 Unauthorized (e.g. token expired)
client.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response && error.response.status === 401) {
            // Clear token and redirect to login if not already there
            // Note: We can't use useNavigate here easily outside component
            // localStorage.removeItem('token');
            // window.location.href = '/login';
            // For now, just reject, let AuthContext handle it
        }
        return Promise.reject(error);
    }
);

export default client;
