# Login issues

## Symptom: redirect loop or blank page after login

- Confirm `FRONTEND_URL` matches the URL in your browser (`http://localhost:5173` vs `http://127.0.0.1:5173`)
- Check Django session cookie domain — use one hostname consistently

## Symptom: 401 on API calls

- Ensure you are logged in via the Vite app (port **5173**), not hitting `:8000` directly for UI
- `VITE_API_BASE_URL` should be empty for local proxy

## Symptom: CSRF errors

- API calls from the React app use session auth through the Vite proxy

Full setup: [Login and first use](../getting-started/login-and-first-use.md) · [auth.md](../auth.md)

Google-specific: [Google OAuth errors](google-oauth-errors.md)
