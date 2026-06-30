# Login and first use

## Set a local password

Bootstrap creates an owner account via migrations. Set a password before signing in:

```bash
INITIAL_USER_PASSWORD='your-local-password' \
  cd backend && .venv/bin/python manage.py set_user_password \
  --email santhoshkgvasudevan@gmail.com
```

Adjust the email if your seed user differs.

## Sign in

1. Open http://127.0.0.1:5173/login
2. Use **email or username** + password
3. Or use **Sign in with Google** (requires OAuth setup — [Configure Google OAuth](../how-to/configure-google-oauth.md))

New users can register at `/register` (creates user, default portfolio, and settings).

## First-use checklist

1. **Portfolio view** — header selector: All Portfolios or a single portfolio
2. **Display currency** — header selector; syncs with Settings
3. **Transactions** — add or import stock/MF rows
4. **Refresh cache** — `make refresh` before trusting dashboard valuations
5. **Dashboard** — summary KPIs and performance chart after cache is warm

## Session behavior

- Session cookies + CSRF; API calls use `credentials: 'include'`
- `401` on protected routes redirects to `/login`

Full auth spec: [Authentication](../auth.md) · Troubleshooting: [Login issues](../troubleshooting/login-issues.md)
