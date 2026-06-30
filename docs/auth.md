# Authentication — KPulla6

## Overview

KPulla6 uses **Django session authentication** for the React SPA and **django-allauth** for Google sign-in. Portfolio data is scoped per user via `Portfolio.user` and `AppSettings.user`.

## Local username/password login

1. Bootstrap the stack: `make bootstrap` (or `make migrate` after pulling auth changes).
2. Set a password for the initial owner (created/linked by migration):

```bash
INITIAL_USER_PASSWORD='your-local-password' \
  cd backend && .venv/bin/python manage.py set_user_password \
  --email santhoshkgvasudevan@gmail.com
```

3. Open `http://localhost:5173/login` and sign in with **email or username** + password.

Registration is also available at `/register` (creates user, default portfolio, and settings).

## Google login setup

1. Create a **Google Cloud OAuth 2.0 Client ID** (Web application).
2. Configure in Google Cloud Console:

| Setting | Local dev value |
|--------|------------------|
| Authorized JavaScript origins | `http://localhost:5173`, `http://127.0.0.1:5173` |
| Authorized redirect URIs | `http://localhost:8000/accounts/google/login/callback/` (must match `GOOGLE_OAUTH_CALLBACK_URL` exactly) |

3. Add to `.env` (see `.env.example`):

```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_OAUTH_CALLBACK_URL=http://localhost:8000/accounts/google/login/callback/
DJANGO_SITE_DOMAIN=localhost:8000
DJANGO_SITE_NAME="Portfolio Insight Local"
FRONTEND_URL=http://localhost:5173
```

Use **`localhost` consistently** for the backend OAuth callback (not `127.0.0.1` on one step and `localhost` on another). A mismatch makes Google return an authorization code, but Django/allauth then fails token exchange and shows **Third-Party Login Failure** (HTTP 401).

4. `DJANGO_SITE_DOMAIN` / `DJANGO_SITE_NAME` update Django `Site` id=1 after `manage.py migrate` (replaces the default `example.com` from initial migrate). Re-run migrate after changing these env vars.
5. Use **Sign in with Google** on the login page (proxied via Vite `/accounts` → Django). With `SOCIALACCOUNT_LOGIN_ON_GET = True`, a GET to `/accounts/google/login/?process=login` redirects straight to Google (no intermediate allauth HTML page). After success, allauth redirects to `FRONTEND_URL/` (see `LOGIN_REDIRECT_URL` in `backend/config/settings.py`), not an allauth signup template.

### Linking Google to the existing owner account

With `SOCIALACCOUNT_EMAIL_AUTHENTICATION` enabled, a Google sign-in whose **verified email** matches an existing user (e.g. `santhoshkgvasudevan@gmail.com` after migration `portfolios.0002_user_ownership`) logs into that user and auto-connects the Google `SocialAccount` — no duplicate user is created.

Secrets must **only** live in `.env` — never in source control.

## Ownership model

| Model | Scoping |
|-------|---------|
| `Portfolio` | `ForeignKey` to `auth.User`; all transactions/holdings derive through portfolio |
| `AppSettings` | `OneToOneField` per user (`display_currency`, `tax_rate_percentage`) |
| Market cache (`HistoricalPrice`, `FXRate`, benchmarks) | Shared global cache; sync endpoints require auth |

Virtual **All Portfolios** remains API-only (`portfolio_scope=all`).

## Existing data assignment

Migration `portfolios.0002_user_ownership` and `settings_app.0002_user_ownership`:

1. Create or reuse user with email `santhoshkgvasudevan@gmail.com`
2. Assign **all** existing portfolios and the legacy singleton settings row to that user
3. Do not delete or truncate existing transactions/prices

Verify after migrate:

```bash
make db-safety-check
```

Transaction/portfolio counts should match the pre-migration snapshot.

## Password reset

- API: `POST /api/v1/auth/password-reset` with `{ "email": "..." }`
- If Django email is not configured, response documents using `set_user_password` instead of sending mail
- With `EMAIL_*` configured, a reset link is emailed to `FRONTEND_URL/reset-password?...`

## API auth endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/auth/csrf` | Set CSRF cookie for session POSTs |
| GET | `/api/v1/auth/me` | Current user |
| POST | `/api/v1/auth/login` | Username/email + password |
| POST | `/api/v1/auth/logout` | End session |
| POST | `/api/v1/auth/register` | Create account |
| POST | `/api/v1/auth/password-reset` | Request reset |

All `/api/v1/*` portfolio/settings/transaction routes require authentication except `GET /api/v1/health`.

## Frontend

- Session cookies + `credentials: 'include'` on API fetches
- `401` on protected APIs redirects to `/login`
- Logout from app header
