"""Episodic memory: what happened, what was decided, what failed.
Written by consolidation from the event bus; read back for context."""
try:
    from memory.store import db, now
except ImportError:
    from app.memory.store import db, now


def log_episode(text: str, importance: float = 1.0) -> dict:
    text = (text or "").strip()[:1000]
    if not text:
        return {"ok": False, "error": "text required"}
    conn = db()
    cur = conn.execute("INSERT INTO mem_episodes(text, importance, ts) VALUES(?,?,?)",
                       (text, max(0.1, min(5.0, importance)), now()))
    conn.commit()
    return {"ok": True, "id": cur.lastrowid}


def recent_episodes(limit: int = 20, since: float = 0):
    rows = db().execute("SELECT id, text, importance, ts FROM mem_episodes WHERE ts>=? ORDER BY ts DESC LIMIT ?",
                        (since, max(1, min(100, limit)))).fetchall()
    return [{"id": r[0], "text": r[1], "importance": r[2], "ts": r[3]} for r in rows]


def forget_before(ts: float) -> int:
    """Decay: drop low-importance episodes older than ts. Returns count."""
    conn = db()
    cur = conn.execute("DELETE FROM mem_episodes WHERE ts<? AND importance<2.0", (ts,))
    conn.commit()
    return cur.rowcount
