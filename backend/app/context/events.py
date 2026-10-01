"""Event bus — every meaningful thing becomes a normalized event.

Producers (email/calendar/goals/approvals/browser/files) emit; the context
engine consumes; wake conditions fire off events, not timers. Table doubles
as the audit trail the event-sourced runtime replays.
"""
import json
import time

try:
    from app.db import connect as _hardb
    from app.paths import data as _pdata
except ImportError:
    from db import connect as _hardb
    from paths import data as _pdata

import os as _os
DB = _pdata("osokai.db")

TYPES = (
    "email.received", "calendar.event.created", "calendar.event.updated",
    "message.received", "browser.page_opened", "file.created", "file.modified",
    "goal.created", "goal.stalled", "goal.completed",
    "approval.requested", "approval.resolved",
    "loop.opened", "loop.due", "loop.closed",
    "bill.expense_added", "bill.settle_reminder",
    "task.completed", "task.failed",
)


def _db():
    db = _hardb(_os.path.normpath(DB))
    db.execute("""CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY, type TEXT, source TEXT, actor TEXT,
        payload TEXT DEFAULT '{}', ts REAL)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_events_type_ts ON events(type, ts)")
    return db


def emit(etype: str, payload: dict = None, source: str = "", actor: str = "") -> dict:
    if etype not in TYPES:
        return {"ok": False, "error": f"unknown event type '{etype}'"}
    try:
        blob = json.dumps(payload or {})[:4000]
        json.loads(blob)  # validate serializable
    except Exception:
        return {"ok": False, "error": "payload must be JSON-serializable"}
    db = _db()
    cur = db.execute("INSERT INTO events(type, source, actor, payload, ts) VALUES(?,?,?,?,?)",
                     (etype, source[:80], actor[:80], blob, time.time()))
    db.commit()
    return {"ok": True, "id": cur.lastrowid}


def list_events(etype: str = "", since: float = 0, limit: int = 50):
    db = _db()
    q = "SELECT id, type, source, actor, payload, ts FROM events WHERE ts>=?"
    args: list = [since]
    if etype:
        q += " AND type=?"
        args.append(etype)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(max(1, min(200, limit)))
    out = []
    for r in db.execute(q, args).fetchall():
        try:
            pl = json.loads(r[4] or "{}")
        except Exception:
            pl = {}
        out.append({"id": r[0], "type": r[1], "source": r[2], "actor": r[3],
                    "payload": pl, "ts": r[5]})
    return out


def latest(etype: str):
    rows = list_events(etype, limit=1)
    return rows[0] if rows else None
