import { useState } from 'react';
import { Link } from 'react-router-dom';
import { requestPasswordReset } from '../../api';
import { Button } from '../../components/ui';
import { AuthShell } from './AuthShell';
import './Auth.css';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');
    setSubmitting(true);
    try {
      const result = await requestPasswordReset(email);
      setMessage(result.detail || 'If an account exists for that email, instructions were sent.');
    } catch (err) {
      setError(err?.message || 'Request failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell title="Reset password" subtitle="Request a password reset link for your account">
      <form className="auth-form" onSubmit={onSubmit}>
        <div className="auth-form__field">
          <label className="auth-form__label" htmlFor="reset-email">
            Email
          </label>
          <input
            id="reset-email"
            type="email"
            className="auth-form__input"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        {error ? <p className="auth-form__error" role="alert">{error}</p> : null}
        {message ? <p className="auth-shell__success" role="status">{message}</p> : null}
        <Button type="submit" variant="primary" className="auth-form__submit" disabled={submitting}>
          {submitting ? 'Sending…' : 'Send reset link'}
        </Button>
      </form>
      <p className="auth-shell__footer">
        <Link to="/login">Back to sign in</Link>
      </p>
    </AuthShell>
  );
}
