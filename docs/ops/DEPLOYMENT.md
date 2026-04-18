# Flowcut Bare-VM Deployment

Target: a single Ubuntu 22.04+ VM with Docker and docker-compose-plugin. Caddy or nginx in front for TLS.

## One-time VM setup

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin git
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"   # log out and back in after this
```

## First deploy

```bash
git clone <repo-url> /opt/flowcut
cd /opt/flowcut
cp .env.example .env
# Edit .env — set SECRET_KEY (openssl rand -hex 32), DATABASE_URL,
# SENTRY_DSN, provider keys. NEVER commit .env to git.

docker compose up -d --build
curl -fsS http://127.0.0.1:8000/healthz
curl -fsS http://127.0.0.1:8000/readyz
curl -fsS -I http://127.0.0.1:3000/
```

## Reverse proxy (Caddy)

`/etc/caddy/Caddyfile`:

```
flowcut.example.com {
    reverse_proxy /api/* 127.0.0.1:8000
    reverse_proxy /billing/* 127.0.0.1:8000
    reverse_proxy /invitations/* 127.0.0.1:8000
    reverse_proxy /static/* 127.0.0.1:8000
    reverse_proxy /healthz 127.0.0.1:8000
    reverse_proxy /readyz 127.0.0.1:8000
    reverse_proxy /ws/* 127.0.0.1:8000
    reverse_proxy 127.0.0.1:3000
}
```

Reload: `sudo systemctl reload caddy`. TLS is automatic via Let's Encrypt.

## Rolling an update

```bash
cd /opt/flowcut
git pull
docker compose build
docker compose up -d
docker compose exec backend sh -c "curl -fsS http://127.0.0.1:8000/readyz"
```

## Rollback

```bash
cd /opt/flowcut
git checkout <previous-sha>
docker compose build
docker compose up -d
# If the previous version expected an older schema:
docker compose exec backend alembic downgrade -1
```

See `docs/ops/MIGRATIONS.md` for migration discipline.

## Health probes

- `GET /healthz` — liveness. Always 200 unless the process is wedged.
- `GET /readyz` — readiness. Returns 503 when the DB is unreachable.

Configure your load balancer / monitor to:
- Restart the container when `/healthz` fails 3 times in a row (Docker `HEALTHCHECK` already does this in `backend/Dockerfile`).
- Hold traffic during deploys until `/readyz` returns 200.

## Backups

Nightly cron:

```bash
0 2 * * * cd /opt/flowcut && docker compose exec -T db pg_dump -U flowcut flowcut | gzip > /var/backups/flowcut-$(date +\%F).sql.gz
```

Keep 14 days. Snapshot the `backend_storage` volume for uploaded media (`docker run --rm -v flowcut_backend_storage:/data -v /var/backups:/out alpine tar czf /out/storage-$(date +%F).tgz -C /data .`).

## Log collection

Logs are JSON on stdout (structlog). The Docker log driver ships them wherever you configure — Loki, ELK, CloudWatch, Papertrail, whatever you already run. Every log line carries `request_id` for correlation with Sentry events.

## Secrets

All secrets live in `/opt/flowcut/.env`. Permissions:

```bash
sudo chown root:docker /opt/flowcut/.env
sudo chmod 640 /opt/flowcut/.env
```

`.env` is in `.gitignore` and `.dockerignore`. Only `.env.example` is committed.

## Monitoring checklist

- Sentry: set `SENTRY_DSN` (backend) and `NEXT_PUBLIC_SENTRY_DSN` (frontend). Errors auto-report with request-id correlation.
- Uptime: hit `/healthz` every 30s from an external monitor (UptimeRobot, Better Uptime, Pingdom).
- Disk: alarm at 80% on `/var/lib/docker` — uploads, DB data, and renders all accumulate there.
- Postgres: at a minimum, monitor connection count and bloat weekly until a dedicated ops pipeline exists.
