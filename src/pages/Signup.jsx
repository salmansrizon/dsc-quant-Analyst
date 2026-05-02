import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate, Link } from 'react-router-dom';

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: '', email: '', phone: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const update = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await signup(form.email, form.phone, form.password, form.full_name);
      navigate('/');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="logo-section">
          <div className="logo-icon">📊</div>
          <h2>Create Account</h2>
          <p>Start tracking Bangladesh stock market</p>
        </div>

        {error && <div className="badge badge-danger" style={{ display: 'block', textAlign: 'center', padding: '8px', marginBottom: '16px' }}>{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="signup-name">Full Name</label>
            <input id="signup-name" className="form-input" placeholder="John Doe" value={form.full_name} onChange={update('full_name')} required />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="signup-email">Email</label>
            <input id="signup-email" className="form-input" type="email" placeholder="you@example.com" value={form.email} onChange={update('email')} required />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="signup-phone">Phone</label>
            <input id="signup-phone" className="form-input" type="tel" placeholder="+880 1XXX-XXXXXX" value={form.phone} onChange={update('phone')} required />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="signup-password">Password</label>
            <input id="signup-password" className="form-input" type="password" placeholder="Min 6 characters" value={form.password} onChange={update('password')} required minLength={6} />
          </div>

          <button className="btn btn-primary btn-lg" type="submit" disabled={loading} style={{ width: '100%' }}>
            {loading ? 'Creating Account...' : 'Create Account'}
          </button>
        </form>

        <div className="auth-footer">
          Already have an account? <Link to="/login">Sign In</Link>
        </div>
      </div>
    </div>
  );
}
