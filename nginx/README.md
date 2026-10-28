# nginx reverse proxy

Puts the web app and the API behind one address. Used by `docker-compose.proxy.yml`.

```bash
docker compose -f docker-compose.yml -f docker-compose.proxy.yml up --build
```

Open http://localhost:8080. The API is at http://localhost:8080/api/ (for example `/api/health`). The API and web ports are not published, so every request passes nginx and its limits. To go back to the direct setup (ports 3000 and 8000): `docker compose down`, then `docker compose up --build`.

## Files

| File | What it is |
|---|---|
| `default.conf` | The server: routes, limits, cache, gzip, timeouts |
| `proxy-api.inc` | Settings shared by every `/api` route (removes `/api`, forwards the client address) |
| `Dockerfile` | The official unprivileged nginx image, pinned, with 3 Alpine packages upgraded for security fixes |
| `tls.example.conf` | A template for HTTPS. Not used by the compose file |

## What it does

| Setting | Value |
|---|---|
| Routes | `/api/*` goes to the API (prefix removed), everything else to the web app |
| Request limit per client address | 20 a second (burst 40, or 60 for pages), 12 a minute for batch uploads, 30 open connections |
| Body size | 1 MB, and 6 MB for the batch upload (the API allows 5 MB files) |
| Client timeouts | 10 s for headers, 15 s for a body (30 s for the upload) |
| Cache | `/api/meta`, `/api/insights` and `/api/template.csv` are kept for 5 minutes. The `X-Cache-Status` header shows `MISS` or `HIT` |
| Compression | gzip for text, JSON, CSV and SVG |
| Errors | `413`, `429` and `502` from nginx itself use the API's `{"detail": [...]}` shape. The API's own errors pass through unchanged |
| Headers | `Server: nginx` without a version. The apps set the other security headers, so nginx adds none |

The web app is built with `NEXT_PUBLIC_API_URL=/api` in this setup, so the browser only talks to one address: no CORS, and the Content Security Policy only needs `'self'`.

The API trusts the client address nginx forwards (`FORWARDED_ALLOW_IPS=*`), which is safe only because nothing else can reach the API. nginx overwrites `X-Forwarded-For`, so a client cannot invent its own address.

## Behind another proxy or a CDN (Cloudflare, a load balancer)

nginx then sees the other proxy's address as the client. Put the real client address first, in `default.conf`, inside `server { ... }`, before the `location` blocks:

```nginx
set_real_ip_from  <the proxy's address range>;
real_ip_header    X-Forwarded-For;
real_ip_recursive on;
```

Without this, all visitors share one rate limit.

## HTTPS (template, not tested here)

Local use is plain HTTP. For a server with a domain, `tls.example.conf` shows what to add. It needs a real domain and certificates, so it could not be checked in this project. Two common ways to get certificates:

- **certbot** on the host (Let's Encrypt), with the certificate folder mounted read-only into the proxy container.
- **Caddy** instead of nginx. It gets and renews certificates by itself. A minimal `Caddyfile`:

  ```
  example.com {
      handle_path /api/* {
          reverse_proxy api:8000
      }
      handle {
          reverse_proxy web:3000
      }
  }
  ```

  Caddy does not have the nginx rate limits, size limits or cache above. The API still has its own limits.

Once HTTPS works everywhere, raise `HSTS_MAX_AGE` when building the web image (it is one day by default, see the root README).
