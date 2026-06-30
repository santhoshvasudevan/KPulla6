# API authentication

Session-based auth for the React SPA. Full spec: [auth.md](../auth.md) · [api-design.md](../api-design.md) § Authentication.

**Base URL:** `http://127.0.0.1:8000/api/v1`

---

## `GET /auth/csrf`

| | |
|---|---|
| **Auth** | Public |
| **Purpose** | CSRF token for mutating requests |

```bash
curl -s -c cookies.txt http://127.0.0.1:8000/api/v1/auth/csrf
```

**Expected:** JSON with `csrfToken` field.

---

## `POST /auth/login`

| | |
|---|---|
| **Auth** | Public |
| **Body** | `username` or `email` + `password` |

```bash
CSRF=$(curl -s -c cookies.txt http://127.0.0.1:8000/api/v1/auth/csrf | python3 -c "import sys,json; print(json.load(sys.stdin)['csrfToken'])")

curl -s -b cookies.txt -c cookies.txt \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $CSRF" \
  -H "Referer: http://127.0.0.1:5173/" \
  -d '{"username":"your@email.com","password":"your-password"}' \
  http://127.0.0.1:8000/api/v1/auth/login
```

**Expected:** `200` with user payload; `cookies.txt` contains `sessionid`.

!!! tip "Easier path"
    Sign in via http://127.0.0.1:5173/login and export cookies from browser devtools for ad-hoc `curl`.

---

## `GET /auth/me`

| | |
|---|---|
| **Auth** | Session required |

```bash
curl -s -b cookies.txt http://127.0.0.1:8000/api/v1/auth/me
```

**Expected:** `200` with current user when logged in; `401` when not.

---

## `POST /auth/logout`

| | |
|---|---|
| **Auth** | Session + CSRF |

Use same CSRF header pattern as login.

---

## Google OAuth

Browser flow only: `GET http://127.0.0.1:8000/accounts/google/login/` → redirects to `FRONTEND_URL` after success.

Setup: [Configure Google OAuth](../how-to/configure-google-oauth.md) · Errors: [Google OAuth errors](../troubleshooting/google-oauth-errors.md)

---

## Common errors

| Status | Meaning |
|--------|---------|
| `401` | No session — log in first |
| `403` | CSRF missing or invalid on POST/PUT/DELETE |

All other `/api/v1/*` endpoints require authentication unless documented as public.

## Next

- [Transactions API](api-transactions.md)

## Related

- [API reference](api-reference.md) · [Login issues](../troubleshooting/login-issues.md)
