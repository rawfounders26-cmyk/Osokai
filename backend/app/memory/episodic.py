"""Episodic memory: what happened, what was decided, what failed.
Written by consolidation from the event bus; read back for context."""
try:
    from memory.store import db, now
except ImportError:
    from app.memory.store import db, now


"""Episodic memory: what happened, what was decided, what failed.
Written by consolidation from the event bus; read back for context.
Write-time dedup merges repeats instead of appending; TTL tiers govern decay."""
try:
    from memory.store import db, now
except ImportError:
    from app.memory.store import db, now

# TTL tiers by importance: short / mid / long / permanent (our own rhythms)
def ttl_for(importance: float) -> float:
    imp = max(0.1, min(5.0, importance))
    if imp < 1.0:
        return 7 * 86400
    if imp < 2.0:
        return 30 * 86400
    if imp < 3.0:
        return 180 * 86400
    return 0  # permanent


def _norm(text: str) -> str:
    import re as _re
    return _re.sub(r"\s+", " ", (text or "").lower()).strip()[:160]


def log_episode(text: str, importance: float = 1.0) -> dict:
    text = (text or "").strip()[:1000]
    if not text:
        return {"ok": False, "error": "text required"}
    conn = db()
    norm, imp = _norm(text), max(0.1, min(5.0, importance))
    # dedup: same story merges and counts up; 3+ sightings promote importance
    dupes = conn.execute(
        "SELECT id, importance, ts FROM mem_episodes ORDER BY ts DESC LIMIT 200").fetchall()
    same = [r for r in dupes if _norm(conn.execute(
        "SELECT text FROM mem_episodes WHERE id=?", (r[0],)).fetchone()[0]) == norm]
    if same:
        first = same[-1]
        try:
            seen_now = conn.execute("SELECT seen FROM mem_episodes WHERE id=?", (first[0],)).fetchone()[0] or 1
        except Exception:
            seen_now = len(same)
        new_seen = seen_now + 1
        new_imp = min(5.0, (first[1] or 1.0) + (0.5 if new_seen >= 3 else 0.0))
        conn.execute("UPDATE mem_episodes SET importance=?, ts=?, seen=? WHERE id=?",
                     (new_imp, now(), new_seen, first[0]))
        for r in same[1:]:
            conn.execute("DELETE FROM mem_episodes WHERE id=?", (r[0],))
        conn.commit()
        return {"ok": True, "id": first[0], "merged": True, "times_seen": new_seen,
                "importance": new_imp}
    cur = conn.execute("INSERT INTO mem_episodes(text, importance, ts) VALUES(?,?,?)",
                       (text, imp, now()))
    conn.commit()
    return {"ok": True, "id": cur.lastrowid, "tier_ttl_days": (ttl_for(imp) // 86400) if ttl_for(imp) else "permanent"}


def recent_episodes(limit: int = 20, since: float = 0):
    rows = db().execute("SELECT id, text, importance, ts FROM mem_episodes WHERE ts>=? ORDER BY ts DESC LIMIT ?",
                        (since, max(1, min(100, limit)))).fetchall()
    return [{"id": r[0], "text": r[1], "importance": r[2], "ts": r[3]} for r in rows]


def forget_before(ts: float = 0) -> int:
    """Tiered decay: each episode lives per its importance tier (ts arg kept
    for backward compat but tiers decide). Returns count."""
    import time as _t
    conn = db()
    rows = conn.execute("SELECT id, importance, ts FROM mem_episodes").fetchall()
    gone = 0
    for rid, imp, rts in rows:
        ttl = ttl_for(imp or 1.0)
        if ttl and rts < _t.time() - ttl:
            conn.execute("DELETE FROM mem_episodes WHERE id=?", (rid,))
            gone += 1
    conn.commit()
    return gone
