import { Link } from 'react-router-dom';
import { Button } from '../../components/ui';
import './Auth.css';

export function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="auth-page">
      <div className="auth-shell">
        <div className="auth-shell__brand">
          <h1 className="auth-shell__logo">Portfolio Insight</h1>
          <p className="auth-shell__subtitle">{subtitle || 'Institutional portfolio analytics'}</p>
        </div>
        {title ? <h2>{title}</h2> : null}
        {children}
        {footer ? <div className="auth-shell__footer">{footer}</div> : null}
      </div>
    </div>
  );
}

export function AuthLinks({ register = false }) {
  return (
    <div className="auth-form__links">
      <Link to="/forgot-password">Forgot password?</Link>
      {register ? (
        <Link to="/register">Register first</Link>
      ) : (
        <Link to="/register">Create account</Link>
      )}
    </div>
  );
}

/** django-allauth Google login entry (proxied to Django; SOCIALACCOUNT_LOGIN_ON_GET redirects immediately). */
export const GOOGLE_LOGIN_PATH = '/accounts/google/login/?process=login';

export function GoogleSignInButton() {
  return (
    <Button
      type="button"
      variant="secondary"
      className="auth-google-btn"
      onClick={() => {
        window.location.assign(GOOGLE_LOGIN_PATH);
      }}
    >
      Sign in with Google
    </Button>
  );
}
