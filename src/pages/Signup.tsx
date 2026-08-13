import { useContext, useState } from 'react';
import type { FormEvent } from 'react';
import type { AxiosInstance } from 'axios';
import { Link, useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import { errorMessage } from '../api/errorMessage';
import { VARIANT_COLOR_VAR } from '../components/ui/Badge';

export default function Signup({ client }: { client: AxiosInstance }) {
  const { login } = useContext(AuthContext);
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: '', email: '', phone: '', password: '' });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const update = (key: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await client.post('/auth/signup', form);
      // Reuse the login flow so AuthContext state + token are populated.
      await login(form.email, form.password);
      navigate('/', { replace: true });
    } catch (err) {
      setError(errorMessage(err, 'Signup failed'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--bg-primary)] px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-8"
        aria-label="Signup form"
      >
        <h1 className="text-2xl font-bold text-center mb-6 text-[var(--accent-blue)]">Create account</h1>
        {(['full_name', 'email', 'phone', 'password'] as const).map((field) => (
          <div className="mb-4" key={field}>
            <label
              htmlFor={field}
              className="block text-sm font-bold mb-2 capitalize text-[var(--text-secondary)]"
            >
              {field.replace('_', ' ')}
            </label>
            <input
              id={field}
              type={field === 'password' ? 'password' : field === 'email' ? 'email' : 'text'}
              required
              value={form[field]}
              onChange={update(field)}
              className="w-full rounded border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-2 text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-blue)]"
            />
          </div>
        ))}
        {error && <p className="text-sm mb-4" style={{ color: VARIANT_COLOR_VAR.negative }}>{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="btn-primary w-full justify-center disabled:opacity-60"
        >
          {submitting ? 'Creating…' : 'Sign up'}
        </button>
        <p className="text-center text-sm mt-4 text-[var(--text-secondary)]">
          Have an account?{' '}
          <Link to="/login" className="text-[var(--accent-blue)] hover:underline">
            Log in
          </Link>
        </p>
      </form>
    </div>
  );
}
