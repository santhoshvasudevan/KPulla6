# Local docs domain

Open the docs site at `http://docs.kpulla6.com:8002` instead of remembering port `8002`.

**Local only.** This hostname works on your Mac unless you configure real DNS.

## Port-based setup (recommended)

### 1. Add hosts entry

```bash
sudo sh -c 'echo "127.0.0.1 docs.kpulla6.com" >> /etc/hosts'
```

Or edit `/etc/hosts` manually:

```text
127.0.0.1 docs.kpulla6.com
```

### 2. Start the stack

```bash
make dev
```

### 3. Open docs

```text
http://docs.kpulla6.com:8002
```

**Verify MkDocs is up:**

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8002/
```

**Expected:** `200`

## All local URLs after `make dev`

| URL | Service |
|-----|---------|
| http://127.0.0.1:5173 | App |
| http://127.0.0.1:8000/api/v1/health | API |
| http://127.0.0.1:8002 | Docs |
| http://docs.kpulla6.com:8002 | Docs (with hosts entry) |

## Optional: no port in the URL

Use a reverse proxy on port 80. **Not required** for `make dev`.

### Caddy

```caddy
docs.kpulla6.com {
    reverse_proxy 127.0.0.1:8002
}
```

**Then open:** http://docs.kpulla6.com

### nginx

```nginx
server {
    listen 80;
    server_name docs.kpulla6.com;
    location / {
        proxy_pass http://127.0.0.1:8002;
    }
}
```

## Notes

- MkDocs binds to `127.0.0.1:8002` only — not exposed on your LAN by default.
- Do not expose this setup to the public internet without TLS and access controls.
