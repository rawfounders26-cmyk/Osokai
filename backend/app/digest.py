"""Proactive research digests — answers delivered before questions are asked.

Interests (topics the user cares about) get nightly depth-1 sweeps via the
scheduler; results compile into the briefing stream with citations.
Instinct answers questions; we deliver answers first.
"""
import os
import sqlite3
import time

try:
    from app.paths import data as _pdata
except ImportError:
    from paths import data as _pdata

DB = _pdata("osokai.db")


def _db():
    db = sqlite3.connect(os.path.normpath(DB), check_same_thread=False)
    db.execute("CREATE TABLE IF NOT EXISTS digest_topics(id INTEGER PRIMARY KEY, topic TEXT, active INT DEFAULT 1, ts REAL)")
    db.execute("""CREATE TABLE IF NOT EXISTS digests(
        id INTEGER PRIMARY KEY, topic TEXT, body TEXT, ts REAL)""")
    return db


def add_topic(topic: str) -> dict:
    topic = (topic or "").strip()[:200]
    if not topic:
        return {"ok": False, "error": "topic required"}
    db = _db()
    cur = db.execute("INSERT INTO digest_topics(topic, ts) VALUES(?,?)", (topic, time.time()))
    db.commit()
    return {"ok": True, "id": cur.lastrowid}


def list_topics():
    return [{"id": r[0], "topic": r[1], "active": bool(r[2])}
            for r in _db().execute("SELECT id, topic, active FROM digest_topics ORDER BY id").fetchall()]


def set_active(tid: int, active: bool) -> dict:
    db = _db()
    db.execute("UPDATE digest_topics SET active=? WHERE id=?", (1 if active else 0, tid))
    db.commit()
    return {"ok": True}


def remove_topic(tid: int) -> dict:
    db = _db()
    db.execute("DELETE FROM digest_topics WHERE id=?", (tid,))
    db.commit()
    return {"ok": True}


def run_digest(topic: str) -> dict:
    """One sweep: research, condense with citations, store + nudge."""
    try:
        try:
            from app.research import deep_research
            from app.proactive import nudge
        except ImportError:
            from research import deep_research
            from proactive import nudge
    except Exception as e:
        return {"ok": False, "note": f"no research engine: {e}"}
    try:
        fp = deep_research(topic, 1)
        body = f"Digest on '{topic}' compiled: {fp}"
        db = _db()
        db.execute("INSERT INTO digests(topic, body, ts) VALUES(?,?,?)", (topic, body[:2000], time.time()))
        db.commit()
        nudge("digest", f"digest:{topic}:{time.strftime('%Y-%m-%d')}", f"📰 {body[:280]}")
        return {"ok": True, "note": body[:300]}
    except Exception as e:
        return {"ok": False, "note": f"{type(e).__name__}: {e}"[:300]}


def run_all() -> dict:
    done = []
    for t in list_topics():
        if t["active"]:
            r = run_digest(t["topic"])
            done.append(f"{t['topic']}: {'ok' if r['ok'] else r['note'][:80]}")
    return {"ok": True, "note": "; ".join(done) or "no active topics"}


def latest(limit: int = 10):
    rows = _db().execute("SELECT id, topic, body, ts FROM digests ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [{"id": r[0], "topic": r[1], "body": r[2], "ts": r[3]} for r in rows]
