# Osok-AI in the cloud — single-tenant brain on your own VPS

Strategy: your VPS is *your* computer in the cloud. Same SQLite brain, same
token auth, same code — plus auto-TLS, encrypted backups, and off-LAN phone
access. No multi-tenant rewrite, no data leaving your control.

## 1. VPS (~$6/mo: Hetzner CX22 / DigitalOcean basic, 2GB RAM, Ubuntu 24.04)

```bash
# on the VPS
curl -fsSL https://get.docker.com | sh
git clone https://github.com/rawfounders26-cmyk/Osokai.git osokai
cd osokai
```

## 2. DNS

Add an `A` record: `osokai.yourdomain.com` → VPS IP. Caddy fetches TLS automatically.

## 3. Secrets + config

```bash
cp backend/.env.example backend/.env
# edit backend/.env: GROQ_API_KEY, SUPABASE_* (optional)
python3 scripts/cloud-secrets.py   # generates OSOKAI_AUTH_TOKEN + OSOKAI_RELAY_KEY
export DOMAIN=osokai.yourdomain.com
```

## 4. Launch

```bash
docker compose -f docker-compose.prod.yml up -d --build
curl https://osokai.yourdomain.com/health
```

## 5. Point your surfaces at the cloud

- **Mobile**: Settings → Backend URL → `https://osokai.yourdomain.com` (same token).
- **Desktop**: Settings → same URL. Works from anywhere now, not just home Wi-Fi.
- **Extension**: popup settings → same URL.
- The relay (`/relay/*`), presence outbox, and offline queue ride HTTPS unchanged.

## 6. Backups (nightly, 7-day retention)

```bash
sudo cp scripts/backup.sh /usr/local/bin/osokai-backup
sudo sh -c 'echo "0 3 * * * root /usr/local/bin/osokai-backup" > /etc/cron.d/osokai'
# test restore on a scratch dir first: scripts/restore.sh <db-backup> [workspace-tgz]
```

## 7. Updates (zero-downtime-ish)

```bash
git pull && docker compose -f docker-compose.prod.yml up -d --build
# rollback: git reset --hard <last-good> && docker compose -f docker-compose.prod.yml up -d --build
```

## 8. Going further (only when you need it)

- **More users**: today one token = one household/team. Per-user auth + data
  isolation is the multi-tenant rewrite — do it when paying users exist, not before.
- **Managed DB**: set `SUPABASE_*` and the memory mirror replicates off-box.
- **Logs**: `docker compose -f docker-compose.prod.yml logs -f caddy osokai`.
- **Lockout**: brute-force token lockout + rate limits already in-app; Caddy adds
  a 300 req/min per-IP shield in front.
