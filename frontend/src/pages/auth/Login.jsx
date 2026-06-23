import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../authContext';
import { Button } from '../../components/ui';
import { AuthLinks, AuthShell, GoogleSignInButton } from './AuthShell';
import './Auth.css';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [usernameOrEmail, setUsernameOrEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await login(usernameOrEmail, password);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err?.message || 'Login failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell title="Sign in" subtitle="Secure access to your portfolio analytics workspace">
      <form className="auth-form" onSubmit={onSubmit}>
        <div className="auth-form__field">
          <label className="auth-form__label" htmlFor="login-identifier">
            Username or email
          </label>
          <input
            id="login-identifier"
            className="auth-form__input"
            autoComplete="username"
            value={usernameOrEmail}
            onChange={(e) => setUsernameOrEmail(e.target.value)}
            required
          />
        </div>
        <div className="auth-form__field">
          <label className="auth-form__label" htmlFor="login-password">
            Password
          </label>
          <input
            id="login-password"
            type="password"
            className="auth-form__input"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        {error ? <p className="auth-form__error" role="alert">{error}</p> : null}
        <AuthLinks register />
        <Button type="submit" variant="primary" className="auth-form__submit" disabled={submitting}>
          {submitting ? 'Signing in…' : 'Sign in'}
        </Button>
        <div className="auth-form__divider">or</div>
        <GoogleSignInButton />
      </form>
      <p className="auth-shell__footer">
        Need an account? <Link to="/register">Register first</Link>
      </p>
    </AuthShell>
  );
}
