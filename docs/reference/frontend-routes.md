# Frontend routes

Main React routes (see `frontend/src/App.jsx`):

| Path | Page |
|------|------|
| `/` | Public landing (signed out) or redirect to `/dashboard` (signed in) |
| `/dashboard` | Dashboard |
| `/login` | Login |
| `/register` | Register |
| `/forgot-password` | Forgot password |
| `/transactions` | Transactions |
| `/cash` | Cash |
| `/assets` | Assets |
| `/fixed-deposits` | Fixed Deposits |
| `/compare` | Compare |
| `/settings` | Settings |

Auth-gated app routes — unauthenticated users redirect to `/login`. Landing does not call portfolio APIs.

Layout reference: [page-layouts.md](../page-layouts.md) · [frontend-design.md](../frontend-design.md)
