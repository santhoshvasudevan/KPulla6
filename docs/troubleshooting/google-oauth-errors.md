# Google OAuth errors

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
