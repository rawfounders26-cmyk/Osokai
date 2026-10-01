"""Device presence + offline outbox — every surface stays in sync.

- `heartbeat(device, meta)` marks a device alive; stale (>10 min) = offline.
- `queue(device, kind, payload)` stashes a message for an offline device.
- `pending(device)` returns + marks delivered; clients poll on app start.
This is what lets the phone pick up exactly where the desktop left off.
"""
import json
import os
import sqlite3
import time

try:
    from app.paths import data as _pdata
except ImportError:
    from paths import data as _pdata

try:
    from app.db import connect as _hardb
except ImportError:
    from db import connect as _hardb
DB = _pdata("osokai.db")
STALE_AFTER = 600
MAX_PAYLOAD_CHARS = 4000


def _db():
    db = _hardb(os.path.normpath(DB))
    db.execute("CREATE TABLE IF NOT EXISTS devices(device TEXT PRIMARY KEY, last_seen REAL, meta TEXT)")
    db.execute("""CREATE TABLE IF NOT EXISTS outbox(
        id INTEGER PRIMARY KEY, device TEXT, kind TEXT, payload TEXT, ts REAL, delivered INTEGER DEFAULT 0)""")
    return db


def heartbeat(device: str, meta: str = "") -> dict:
    db = _db()
    db.execute("INSERT OR REPLACE INTO devices(device, last_seen, meta) VALUES(?,?,?)",
               (device, time.time(), meta[:500]))
    db.commit()
    items = pending(device)
    return {"ok": True, "pending": items, "devices": list_devices()}


def list_devices():
    db = _db()
    now = time.time()
    rows = db.execute("SELECT device, last_seen, meta FROM devices ORDER BY last_seen DESC").fetchall()
    return [{"device": r[0], "online": (now - r[1]) < STALE_AFTER,
             "last_seen": r[1], "meta": r[2]} for r in rows]


def queue(device: str, kind: str, payload: dict) -> dict:
    try:
        blob = json.dumps(payload)
    except Exception:
        return {"ok": False, "error": "payload must be JSON-serializable"}
    if len(blob) > MAX_PAYLOAD_CHARS:
        return {"ok": False, "error": f"payload too large (>{MAX_PAYLOAD_CHARS} chars)"}
    db = _db()
    cur = db.execute("INSERT INTO outbox(device, kind, payload, ts) VALUES(?,?,?,?)",
                     (device, kind, blob, time.time()))
    db.commit()
    return {"ok": True, "id": cur.lastrowid}


def pending(device: str, limit: int = 20):
    """Read-only fetch. Clients ack received IDs separately — nothing auto-marks."""
    db = _db()
    rows = db.execute("SELECT id, kind, payload, ts FROM outbox WHERE device=? AND delivered=0 ORDER BY id LIMIT ?",
                      (device, max(1, min(100, limit)))).fetchall()
    out = []
    for r in rows:
        try:
            pl = json.loads(r[2])
        except Exception:
            continue  # quarantine malformed rows, keep serving the rest
        out.append({"id": r[0], "kind": r[1], "payload": pl, "ts": r[3]})
    return out


def ack(device: str, ids) -> dict:
    try:
        clean = [int(i) for i in (ids or [])]
    except Exception:
        return {"ok": False, "error": "ids must be integers"}
    if not clean:
        return {"ok": True, "acked": 0}
    db = _db()
    cur = db.execute(f"UPDATE outbox SET delivered=1 WHERE device=? AND delivered=0 AND id IN ({','.join('?' * len(clean))})",
                     (device, *clean))
    db.commit()
    return {"ok": True, "acked": cur.rowcount}
