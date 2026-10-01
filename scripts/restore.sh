#!/bin/sh
# Restore (F11): decrypts, integrity-checks, clears stale WAL, restores into the
# real Compose volume, restarts. Includes a --drill mode that restores into a
# scratch container and runs integrity_check WITHOUT touching production.
# Usage: restore.sh <db.enc> [workspace-tgz.enc] | restore.sh --drill <db.enc>
# Env: OSOKAI_BACKUP_KEY (required), COMPOSE_PROJECT (default osokai).
set -eu
[ -n "${OSOKAI_BACKUP_KEY:-}" ] || { echo "FATAL: OSOKAI_BACKUP_KEY unset"; exit 1; }
PROJ="${COMPOSE_PROJECT:-osokai}"
VOL="$PROJ-osokai-data"

decrypt() { # $1 in.enc $2 out
  python3 - "$1" "$2" <<'EOF'
import sys
from cryptography.fernet import Fernet
import os
raw = open(sys.argv[1], "rb").read()
open(sys.argv[2], "wb").write(Fernet(os.environ["OSOKAI_BACKUP_KEY"].encode()).decrypt(raw))
EOF
}

if [ "${1:-}" = "--drill" ]; then
  DB_BAK="${2:?usage: restore.sh --drill <db.enc>}"
  TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
  decrypt "$DB_BAK" "$TMP/drill.db"
  sqlite3 "$TMP/drill.db" "PRAGMA integrity_check;" | grep -q "^ok$" \
    && echo "DRILL PASS: backup decrypts and integrity-checks clean" \
    || { echo "DRILL FAIL"; exit 1; }
  exit 0
fi

DB_BAK="${1:?usage: restore.sh <db-backup.enc> [workspace-tgz.enc]}"
WS_BAK="${2:-}"
MP="$(docker volume inspect "$VOL" --format '{{.Mountpoint}}' 2>/dev/null || true)"
[ -n "$MP" ] || { echo "FATAL: volume $VOL not found"; exit 1; }

docker compose -f docker-compose.prod.yml down
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
decrypt "$DB_BAK" "$TMP/osokai.db"
sqlite3 "$TMP/osokai.db" "PRAGMA integrity_check;" | grep -q "^ok$" \
  || { echo "FATAL: backup corrupt, production left stopped — investigate"; exit 1; }
# clear stale WAL/SHM so the restored db opens cleanly
rm -f "$MP"/osokai.db-wal "$MP"/osokai.db-shm "$MP"/osokai.db-journal
cp "$TMP/osokai.db" "$MP/osokai.db"
if [ -n "$WS_BAK" ]; then
  decrypt "$WS_BAK" "$TMP/ws.tgz"
  rm -rf "$MP/workspace"
  mkdir -p "$MP/workspace"
  tar -xzf "$TMP/ws.tgz" -C "$MP" || { echo "FATAL: workspace restore failed"; exit 1; }
fi
docker compose -f docker-compose.prod.yml up -d
echo "restored, stack restarted"
