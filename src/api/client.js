const API_BASE = import.meta.env.VITE_API_URL || '';

/**
 * Fetch wrapper with JWT injection.
 */
async function request(path, options = {}) {
  const token = localStorage.getItem('token');
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/login';
    return;
  }

  if (!res.ok) {
    const contentType = res.headers.get('content-type') || '';
    let detail = res.statusText || 'Request failed';

    if (contentType.includes('application/json')) {
      const err = await res.json().catch(() => null);
      detail = err?.detail || err?.message || detail;
    } else {
      const text = await res.text().catch(() => 'Request failed');
      if (text) detail = text.trim().slice(0, 300);
    }

    throw new Error(detail || 'Request failed');
  }

  return res.json();
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body: JSON.stringify(body) }),
  put: (path, body) => request(path, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (path) => request(path, { method: 'DELETE' }),
};

export default api;
