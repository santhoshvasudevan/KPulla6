# Environment variables

Key variables (see `.env.example` in repo root):

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres connection |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | OAuth |
| `GOOGLE_OAUTH_CALLBACK_URL` | Must match Google Console |
| `FRONTEND_URL` | Post-login redirect |
| `DJANGO_SITE_DOMAIN` | django-allauth Sites |
| `VITE_API_BASE_URL` | Empty for local proxy; set for custom API host |

OAuth setup: [Configure Google OAuth](../how-to/configure-google-oauth.md)

Full auth doc: [auth.md](../auth.md)
