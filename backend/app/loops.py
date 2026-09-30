"""Open Loops — intentions (reply/call/save/promise/habit) captured anywhere,
nudged at the right time, closed from anywhere. One state on every surface."""
import sqlite3
import os
import time

DB = os.path.join(os.path.dirname(__file__), "..", "osokai.db")

def _db():
    db = sqlite3.connect(os.path.normpath(DB), check_same_thread=False)
    db.execute("""CREATE TABLE IF NOT EXISTS loops(
        id INTEGER PRIMARY KEY, kind TEXT, title TEXT, source TEXT,
        due REAL DEFAULT 0, repeat TEXT DEFAULT '', status TEXT DEFAULT 'open',
        created REAL, closed REAL DEFAULT 0)""")
    return db

def add(kind: str, title: str, source: str = "chat", due: float = 0, repeat: str = ""):
    db = _db()
    cur = db.execute("INSERT INTO loops(kind, title, source, due, repeat, status, created) VALUES(?,?,?,?,?,?,?)",
                     (kind or "promise", title, source, due, repeat, "open", time.time()))
    db.commit()
    return {"ok": True, "id": cur.lastrowid}

def list_loops(status: str = ""):
    db = _db()
    q = "SELECT id, kind, title, source, due, repeat, status, created, closed FROM loops"
    args = []
    if status:
        q += " WHERE status=?"
        args.append(status)
    q += " ORDER BY CASE WHEN due>0 THEN due ELSE 9999999999 END, id DESC"
    return [{"id": r[0], "kind": r[1], "title": r[2], "source": r[3], "due": r[4],
             "repeat": r[5], "status": r[6], "created": r[7], "closed": r[8]}
            for r in db.execute(q, args)]

def close(lid: int):
    db = _db()
    r = db.execute("SELECT repeat FROM loops WHERE id=? AND status='open'", (lid,)).fetchone()
    if not r:
        return {"ok": False, "error": "not open"}
    if r[0] in ("daily", "weekly"):
        import datetime
        nxt = time.time() + (86400 if r[0] == "daily" else 7 * 86400)
        db.execute("UPDATE loops SET due=?, closed=? WHERE id=?", (nxt, time.time(), lid))
    else:
        db.execute("UPDATE loops SET status='done', closed=? WHERE id=?", (time.time(), lid))
    db.commit()
    return {"ok": True, "id": lid}

def close_by_title(text: str):
    """'done replying to ravi' -> closes best match. Returns match or {}. """
    import re
    words = [w for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in ("done", "the", "and", "for", "with")]
    if not words:
        return {}
    db = _db()
    rows = db.execute("SELECT id, kind, title FROM loops WHERE status='open' ORDER BY id DESC").fetchall()
    best, score = None, 0
    for i, k, t in rows:
        s = sum(1 for w in words if w in (t or "").lower())
        if s > score:
            best, score = i, s
    if best and score > 0:
        close(best)
        return {"id": best}
    return {}

def due_now():
    now = time.time()
    db = _db()
    return [{"id": r[0], "kind": r[1], "title": r[2]}
            for r in db.execute("SELECT id, kind, title FROM loops WHERE status='open' AND due>0 AND due<=?", (now,))]

def snooze_approval(aid: int, hours: float = 3):
    """Missed approval -> loop. Returns loop record id."""
    r = add("promise", f"Decide approval #{aid}", source="approval", due=time.time() + hours * 3600)
    return r
