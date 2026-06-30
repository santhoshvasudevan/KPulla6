# Login and first use

Sign in after bootstrap and confirm the app is usable.

## Prerequisites

```bash
make dev
```

**Expected:** app at http://127.0.0.1:5173 · API health at http://127.0.0.1:8000/api/v1/health

## 1. Set a local password

Bootstrap creates an owner account. Set a password before signing in:

```bash
INITIAL_USER_PASSWORD='your-local-password' \
  cd backend && .venv/bin/python manage.py set_user_password \
  --email santhoshkgvasudevan@gmail.com
```

**Expected:** `Password set for user …`

Change the email if your seed user differs.

## 2. Sign in

1. Open http://127.0.0.1:5173/login
2. Enter **email or username** + password
3. **Expected:** redirect to the dashboard

**Google sign-in:** requires OAuth in `.env` — [Configure Google OAuth](../how-to/configure-google-oauth.md)

**New user:** register at http://127.0.0.1:5173/register (creates user, default portfolio, settings).

## 3. First-use checklist

| Step | Where | Why |
|------|-------|-----|
| Pick portfolio scope | Header **Portfolio view** | Scopes transactions, holdings, summary |
| Pick display currency | Header currency selector | FX for non-base holdings |
| Add or import data | **Transactions** | Source of truth for holdings |
| Warm the cache | Terminal: `make refresh` | Dashboard needs cached prices/NAVs |
| Review dashboard | **Dashboard** | KPIs + performance chart |

**After refresh:**

```bash
make refresh
```

**Expected:** `Refresh complete (stocks, benchmarks, FX, mutual fund NAVs)`

Tutorial: [Refresh market data](../tutorials/refresh-market-data.md)

## Session notes

- API calls use session cookies + CSRF from the Vite app (port **5173**)
- `401` on protected routes redirects to `/login`

**Problems?** [Login issues](../troubleshooting/login-issues.md) · Full spec: [auth.md](../auth.md)
