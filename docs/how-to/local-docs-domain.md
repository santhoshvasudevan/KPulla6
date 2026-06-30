# Local docs domain

Use a friendly hostname for the documentation site on your Mac. **Local only** unless you configure real DNS.

## Simple port-based setup

Add to `/etc/hosts`:

```text
127.0.0.1 docs.kpulla6.com
```

Start the stack:

```bash
make dev
```

Open:

```text
http://docs.kpulla6.com:8002
```

MkDocs listens on `127.0.0.1:8002` (see `dev_addr` in `mkdocs.yml`).

## URLs after `make dev`

| URL | Service |
|-----|---------|
| http://127.0.0.1:5173 | App |
| http://127.0.0.1:8000/api/v1/health | API |
| http://127.0.0.1:8002 | Docs |
| http://docs.kpulla6.com:8002 | Docs (with hosts entry) |

## Optional no-port setup

Run a local reverse proxy so you can open `http://docs.kpulla6.com` without `:8002`.

### Caddy (preferred example)

```caddy
docs.kpulla6.com {
    reverse_proxy 127.0.0.1:8002
}
```

Then:

```text
http://docs.kpulla6.com
```

### nginx (alternative)

```nginx
server {
    listen 80;
    server_name docs.kpulla6.com;
    location / {
        proxy_pass http://127.0.0.1:8002;
    }
}
```

The proxy is **optional**. `make dev` does not require it.

## Notes

- `site_url` in `mkdocs.yml` is set to `http://docs.kpulla6.com/` for correct relative links when using the local domain.
- Do not expose this setup to the public internet without proper TLS and access controls.
