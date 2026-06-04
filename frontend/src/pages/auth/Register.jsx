import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../authContext';
import { Button } from '../../components/ui';
import { AuthShell, GoogleSignInButton } from './AuthShell';
import './Auth.css';

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    password_confirm: '',
  });
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const onChange = (field) => (e) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await register(form);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err?.message || 'Registration failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell title="Create account" subtitle="Start tracking portfolios with cached valuation analytics">
      <form className="auth-form" onSubmit={onSubmit}>
        <div className="auth-form__field">
          <label className="auth-form__label" htmlFor="register-username">
            Username
          </label>
          <input
            id="register-username"
            className="auth-form__input"
            autoComplete="username"
            value={form.username}
            onChange={onChange('username')}
            required
          />
        </div>
        <div className="auth-form__field">
          <label className="auth-form__label" htmlFor="register-email">
            Email
          </label>
          <input
            id="register-email"
            type="email"
            className="auth-form__input"
            autoComplete="email"
            value={form.email}
            onChange={onChange('email')}
            required
          />
        </div>
        <div className="auth-form__field">
          <label className="auth-form__label" htmlFor="register-password">
            Password
          </label>
          <input
            id="register-password"
            type="password"
            className="auth-form__input"
            autoComplete="new-password"
            value={form.password}
            onChange={onChange('password')}
            required
          />
        </div>
        <div className="auth-form__field">
          <label className="auth-form__label" htmlFor="register-password-confirm">
            Confirm password
          </label>
          <input
            id="register-password-confirm"
            type="password"
            className="auth-form__input"
            autoComplete="new-password"
            value={form.password_confirm}
            onChange={onChange('password_confirm')}
            required
          />
        </div>
        {error ? <p className="auth-form__error">{error}</p> : null}
        <Button type="submit" disabled={submitting}>
          {submitting ? 'Creating account…' : 'Register'}
        </Button>
        <div className="auth-form__divider">or</div>
        <GoogleSignInButton />
      </form>
      <p className="auth-shell__footer">
        Already registered? <Link to="/login">Sign in</Link>
      </p>
    </AuthShell>
  );
}
