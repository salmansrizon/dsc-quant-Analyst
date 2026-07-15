import { useContext, useState } from 'react';
import type { FormEvent } from 'react';
import type { AxiosInstance } from 'axios';
import { Link, useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';

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
      const message =
        (err as { response?: { data?: { detail?: string } }; message?: string })
          ?.response?.data?.detail ??
        (err as Error)?.message ??
        'Signup failed';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm bg-white p-8 rounded-lg shadow"
        aria-label="Signup form"
      >
        <h1 className="text-2xl font-bold text-center mb-6 text-indigo-600">Create account</h1>
        {(['full_name', 'email', 'phone', 'password'] as const).map((field) => (
          <div className="mb-4" key={field}>
            <label htmlFor={field} className="block text-gray-700 text-sm font-bold mb-2 capitalize">
              {field.replace('_', ' ')}
            </label>
            <input
              id={field}
              type={field === 'password' ? 'password' : field === 'email' ? 'email' : 'text'}
              required
              value={form[field]}
              onChange={update(field)}
              className="shadow-sm appearance-none border rounded w-full py-2 px-3 text-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        ))}
        {error && <p className="text-red-500 text-sm mb-4">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white font-bold py-2 px-4 rounded-md"
        >
          {submitting ? 'Creating…' : 'Sign up'}
        </button>
        <p className="text-center text-sm text-gray-600 mt-4">
          Have an account?{' '}
          <Link to="/login" className="text-indigo-600 hover:underline">
            Log in
          </Link>
        </p>
      </form>
    </div>
  );
}
