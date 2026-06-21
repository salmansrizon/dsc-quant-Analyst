const API_BASE = '/api';
let currentToken = null;

const apiClient = {
  setToken: (token) => {
    currentToken = token;
  },
  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };
    if (currentToken) {
      headers['Authorization'] = `Bearer ${currentToken}`;
    }
    const response = await fetch(url, { ...options, headers });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || 'Request failed');
    }
    return response.json();
  },
  get: (endpoint, options) => apiClient.request(endpoint, { ...options, method: 'GET' }),
  post: (endpoint, body, options) => apiClient.request(endpoint, { ...options, method: 'POST', body: JSON.stringify(body) }),
  put: (endpoint, body, options) => apiClient.request(endpoint, { ...options, method: 'PUT', body: JSON.stringify(body) }),
  delete: (endpoint, options) => apiClient.request(endpoint, { ...options, method: 'DELETE' }),
};

export default apiClient;
