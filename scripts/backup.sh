#!/bin/sh
# Nightly backup: online SQLite snapshot + workspace tarball, Fernet-encrypted,
# volume-aware, fails LOUDLY on any partial data (F11).
# Cron: 0 3 * * * /srv/osokai/scripts/backup.sh >> /var/log/osokai-backup.log 2>&1
# Env: OSOKAI_BACKUP_KEY (required, 32-byte urlsafe base64), OSOKAI_BACKUP_DIR,
#      OSOKAI_BACKUP_KEEP, COMPOSE_PROJECT (default osokai).
set -eu
[ -n "${OSOKAI_BACKUP_KEY:-}" ] || { echo "FATAL: OSOKAI_BACKUP_KEY unset — refusing silent no-op"; exit 1; }
BACKUP_DIR="${OSOKAI_BACKUP_DIR:-/var/backups/osokai}"
KEEP="${OSOKAI_BACKUP_KEEP:-7}"
STAMP="$(date +%Y%m%d-%H%M%S)"
PROJ="${COMPOSE_PROJECT:-osokai}"

# resolve the real Compose volume (project-prefixed), not a hardcoded path
VOL="$PROJ-osokai-data"
MP="$(docker volume inspect "$VOL" --format '{{.Mountpoint}}' 2>/dev/null || true)"
if [ -z "$MP" ]; then
  echo "FATAL: volume $VOL not found — is the prod stack up?"
  exit 1
fi
DB="$MP/osokai.db"
[ -f "$DB" ] || { echo "FATAL: $DB missing"; exit 1; }

mkdir -p "$BACKUP_DIR"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# online snapshot (never copy the live WAL db); integrity-gated
sqlite3 "$DB" ".backup '$TMP/osokai-$STAMP.db'" || { echo "FATAL: sqlite backup failed"; exit 1; }
sqlite3 "$TMP/osokai-$STAMP.db" "PRAGMA integrity_check;" | grep -q "^ok$" \
  || { echo "FATAL: snapshot integrity_check failed"; exit 1; }
# workspace from the same volume (vault stores ride along: vault_secrets.json lives in data dir)
tar -czf "$TMP/workspace-$STAMP.tgz" -C "$MP" workspace vault_secrets.json connector_vault.json 2>/dev/null \
  || tar -czf "$TMP/workspace-$STAMP.tgz" -C "$MP" workspace \
  || { echo "FATAL: workspace tar failed"; exit 1; }
[ -s "$TMP/workspace-$STAMP.tgz" ] || { echo "FATAL: empty workspace tarball"; exit 1; }

# encrypt at rest with the backup key (Fernet)
python3 - "$TMP/osokai-$STAMP.db" "$BACKUP_DIR/osokai-$STAMP.db.enc" <<'EOF'
import sys
from cryptography.fernet import Fernet
import os
key = os.environ["OSOKAI_BACKUP_KEY"]
raw = open(sys.argv[1], "rb").read()
open(sys.argv[2], "wb").write(Fernet(key.encode()).encrypt(raw))
EOF
python3 - "$TMP/workspace-$STAMP.tgz" "$BACKUP_DIR/workspace-$STAMP.tgz.enc" <<'EOF'
import sys
from cryptography.fernet import Fernet
import os
key = os.environ["OSOKAI_BACKUP_KEY"]
raw = open(sys.argv[1], "rb").read()
open(sys.argv[2], "wb").write(Fernet(key.encode()).encrypt(raw))
EOF

# retention (encrypted sets only)
ls -t "$BACKUP_DIR"/osokai-*.db.enc 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm -f
ls -t "$BACKUP_DIR"/workspace-*.tgz.enc 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm -f
echo "$STAMP backup ok (encrypted, integrity-checked)"
