import { Link } from 'react-router-dom';
import { Button } from '../../components/ui';
import './Auth.css';

export function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="auth-page">
      <div className="auth-shell">
        <header className="auth-shell__brand">
          <div className="auth-shell__brand-mark" aria-hidden="true">
            K
          </div>
          <div className="auth-shell__brand-copy">
            <p className="auth-shell__eyebrow">Executive Portfolio OS</p>
            <h1 className="auth-shell__logo">KPulla6</h1>
            {subtitle ? <p className="auth-shell__tagline">{subtitle}</p> : null}
          </div>
        </header>

        <div className="auth-shell__panel">
          {title ? <h2 className="auth-shell__title">{title}</h2> : null}
          {children}
        </div>

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

/**
 * Hosts that do not share cookies with `localhost`.
 * The OAuth callback is `http://localhost:8000/...`, so the session cookie
 * must be set on `localhost` or allauth cannot recover the login state.
 */
const LOOPBACK_HOSTS = new Set(['127.0.0.1', '::1', '[::1]']);

export function resolveGoogleLoginUrl(locationLike = window.location) {
  const hostname = locationLike?.hostname || '';
  if (!LOOPBACK_HOSTS.has(hostname)) {
    return GOOGLE_LOGIN_PATH;
  }
  const port = locationLike.port || '5173';
  return `http://localhost:${port}${GOOGLE_LOGIN_PATH}`;
}

export function GoogleSignInButton() {
  return (
    <Button
      type="button"
      variant="secondary"
      className="auth-google-btn"
      onClick={() => {
        window.location.assign(resolveGoogleLoginUrl(window.location));
      }}
    >
      Sign in with Google
    </Button>
  );
}
