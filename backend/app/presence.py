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
    db = _db()
    cur = db.execute("INSERT INTO outbox(device, kind, payload, ts) VALUES(?,?,?,?)",
                     (device, kind, json.dumps(payload)[:4000], time.time()))
    db.commit()
    return {"ok": True, "id": cur.lastrowid}


def pending(device: str, limit: int = 20):
    db = _db()
    rows = db.execute("SELECT id, kind, payload, ts FROM outbox WHERE device=? AND delivered=0 ORDER BY id LIMIT ?",
                      (device, limit)).fetchall()
    out = []
    for r in rows:
        try:
            pl = json.loads(r[2])
        except Exception:
            pl = {"text": r[2]}
        out.append({"id": r[0], "kind": r[1], "payload": pl, "ts": r[3]})
    if rows:
        db.execute("UPDATE outbox SET delivered=1 WHERE device=? AND delivered=0", (device,))
        db.commit()
    return out
