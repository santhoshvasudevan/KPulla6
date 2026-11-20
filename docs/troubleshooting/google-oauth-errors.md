# Google OAuth errors

## Third-Party Login Failure (HTTP 401)

Google can return an authorization code while django-allauth still shows **Third-Party Login Failure**. The OAuth session cookie and the callback must share the host `localhost`.

`GOOGLE_OAUTH_CALLBACK_URL` is `http://localhost:8000/accounts/google/login/callback/`. Opening the app at `http://127.0.0.1:5173` stores that cookie on `127.0.0.1`. The callback on `localhost` never receives it, so allauth cannot find the login state and returns 401.

**Sign in with Google** switches `127.0.0.1` and `::1` to `http://localhost:<same port>` before starting OAuth. After success, allauth sends you to `FRONTEND_URL` (`http://localhost:5173`).

## `redirect_uri_mismatch`

Authorized redirect URI in Google Console must be exactly:

```text
http://localhost:8000/accounts/google/login/callback/
```

Match `GOOGLE_OAUTH_CALLBACK_URL` in `.env`. Do not mix `127.0.0.1` and `localhost`.

## `invalid_client`

Check `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`. Restart Django after changes.

## Site ID / domain errors

Run `make migrate` after changing `DJANGO_SITE_DOMAIN`. See [auth.md](../auth.md).

How-to: [Configure Google OAuth](../how-to/configure-google-oauth.md)
