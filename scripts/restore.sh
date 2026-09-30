#!/bin/sh
# Restore: scripts/restore.sh /var/backups/osokai/osokai-YYYYMMDD-HHMMSS.db [workspace-tgz]
# Stops the stack first, restores, restarts. Run from the repo dir.
set -eu
DB_BAK="${1:?usage: restore.sh <db-backup> [workspace-tgz]}"
WS_BAK="${2:-}"
VOL="$(docker volume inspect osokai-data --format '{{.Mountpoint}}' 2>/dev/null || echo /var/lib/docker/volumes/osokai-data/_data)"

docker compose -f docker-compose.prod.yml down
cp "$DB_BAK" "$VOL/osokai.db"
if [ -n "$WS_BAK" ]; then
  rm -rf "$VOL/workspace"
  mkdir -p "$VOL/workspace"
  tar -xzf "$WS_BAK" -C "$VOL"
fi
docker compose -f docker-compose.prod.yml up -d
echo "restored, stack restarted"
