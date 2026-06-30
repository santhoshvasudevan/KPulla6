# Run the app on iPad / LAN

Use the full React app from another device on the same Wi-Fi.

## On the Mac

```bash
make dev
ipconfig getifaddr en0   # Wi-Fi LAN IP
```

## On iPad / other device

Open:

```text
http://<mac-lan-ip>:5173
```

Do **not** use port `:8000` directly from the device.

## `.env`

Keep `VITE_API_BASE_URL` **empty** so the Vite proxy forwards `/api` to Django on the Mac.

## Checklist

| Check | Action |
|-------|--------|
| Same Wi-Fi | Avoid guest/isolated VLAN |
| Firewall | Allow Node (Vite) if macOS prompts |
| API calls | Should go to `http://<mac-ip>:5173/api/v1/...` only |

Full workflow: [workflows.md — iPad / LAN](../workflows.md)
