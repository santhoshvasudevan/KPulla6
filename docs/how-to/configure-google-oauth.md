# Configure Google OAuth

## Google Cloud Console

Create an OAuth 2.0 **Web application** client.

| Setting | Local dev |
|---------|-----------|
| Authorized JavaScript origins | `http://localhost:5173`, `http://127.0.0.1:5173` |
| Authorized redirect URIs | `http://localhost:8000/accounts/google/login/callback/` |

Use **`localhost` consistently** for the callback — mixing `127.0.0.1` and `localhost` breaks token exchange.

## `.env`

```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_OAUTH_CALLBACK_URL=http://localhost:8000/accounts/google/login/callback/
DJANGO_SITE_DOMAIN=localhost:8000
DJANGO_SITE_NAME="Portfolio Insight Local"
FRONTEND_URL=http://localhost:5173
```

Run `make migrate` after changing site domain vars.

## Test

Login page → **Sign in with Google** → redirect back to `FRONTEND_URL/`.

Troubleshooting: [Google OAuth errors](../troubleshooting/google-oauth-errors.md)

Full spec: [auth.md](../auth.md)
