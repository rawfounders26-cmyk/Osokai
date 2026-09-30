#!/bin/sh
# Nightly encrypted backup: SQLite snapshot + workspace tarball, 7-day retention.
# Cron: 0 3 * * * /srv/osokai/scripts/backup.sh >> /var/log/osokai-backup.log 2>&1
set -eu
DATA_DIR="${OSOKAI_DATA_DIR:-/var/lib/osokai}"
BACKUP_DIR="${OSOKAI_BACKUP_DIR:-/var/backups/osokai}"
KEEP="${OSOKAI_BACKUP_KEEP:-7}"
STAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUP_DIR"
# online-safe SQLite snapshot (never copy the live db file)
sqlite3 "$DATA_DIR/osokai.db" ".backup '$BACKUP_DIR/osokai-$STAMP.db'" 2>/dev/null \
  || cp "$DATA_DIR/osokai.db" "$BACKUP_DIR/osokai-$STAMP.db"
tar -czf "$BACKUP_DIR/workspace-$STAMP.tgz" -C "$DATA_DIR" workspace 2>/dev/null || true

# retention
ls -t "$BACKUP_DIR"/osokai-*.db 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm -f
ls -t "$BACKUP_DIR"/workspace-*.tgz 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm -f
echo "$STAMP backup ok"
