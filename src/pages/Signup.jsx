import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { BarChart2, ArrowRight } from 'lucide-react';
import { colors } from '../design';

const inputStyle = {
  background: colors.surface2,
  border: `1px solid ${colors.border}`,
  borderRadius: 8,
  color: colors.textPrimary,
  padding: '10px 14px',
  fontSize: 14,
  width: '100%',
  lineHeight: 1.4,
};

const FIELDS = [
  { key: 'full_name', label: 'Full name',  type: 'text',     placeholder: 'Jane Smith',       autoComplete: 'name' },
  { key: 'email',     label: 'Email',       type: 'email',    placeholder: 'you@example.com',  autoComplete: 'email' },
  { key: 'phone',     label: 'Phone',       type: 'tel',      placeholder: '+880…',            autoComplete: 'tel' },
  { key: 'password',  label: 'Password',    type: 'password', placeholder: '••••••••',         autoComplete: 'new-password' },
];

export const SignupPage = () => {
  const [form, setForm] = useState({ email: '', phone: '', password: '', full_name: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { signup } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await signup(form);
      navigate('/');
    } catch (err) {
      setError(err.message || 'Signup failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh', background: colors.bg,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: "'Ubuntu', -apple-system, sans-serif",
      position: 'relative', overflow: 'hidden',
    }}>
      <div className="auth-bg-glow" />

      <div style={{
        width: 400, position: 'relative', zIndex: 1,
        background: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: 16,
        padding: '36px 32px',
        boxShadow: 'var(--shadow-lg)',
      }}>
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 32 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 9, flexShrink: 0,
            background: 'var(--gradient-brand)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 2px 10px rgba(59,126,248,0.4)',
          }}>
            <BarChart2 size={18} color="#fff" aria-hidden="true" />
          </div>
          <span style={{ fontSize: 16, fontWeight: 700, color: colors.textPrimary, letterSpacing: -0.4 }}>
            DSC <span style={{ color: colors.accent }}>Quant</span>
          </span>
        </div>

        <h1 style={{ color: colors.textPrimary, fontSize: 22, fontWeight: 700, letterSpacing: -0.5, marginBottom: 6 }}>
          Create your account
        </h1>
        <p style={{ color: colors.textSecondary, fontSize: 13, marginBottom: 28, lineHeight: 1.5 }}>
          Start tracking your portfolio and market alerts
        </p>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {FIELDS.map(({ key, label, type, placeholder, autoComplete }) => (
            <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label htmlFor={`signup-${key}`} style={{ color: colors.textSecondary, fontSize: 12, fontWeight: 500 }}>
                {label}
              </label>
              <input
                id={`signup-${key}`}
                type={type}
                placeholder={placeholder}
                required
                autoComplete={autoComplete}
                value={form[key]}
                onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                style={inputStyle}
              />
            </div>
          ))}

          {error && (
            <div role="alert" style={{
              color: colors.red, fontSize: 13, padding: '10px 12px',
              background: 'rgba(240,82,82,0.08)', borderRadius: 7,
              border: `1px solid rgba(240,82,82,0.2)`,
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              background: colors.accent, color: '#fff', border: 'none', borderRadius: 8,
              padding: '11px 16px', fontSize: 14, fontWeight: 600, cursor: 'pointer',
              opacity: loading ? 0.7 : 1, marginTop: 4,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            }}
          >
            {loading ? 'Creating account…' : <><span>Create Account</span><ArrowRight size={15} aria-hidden="true" /></>}
          </button>
        </form>

        <p style={{ marginTop: 24, textAlign: 'center', fontSize: 13, color: colors.textSecondary }}>
          Already have an account?{' '}
          <Link to="/login" style={{ color: colors.accent, textDecoration: 'none', fontWeight: 500 }}>
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
};
