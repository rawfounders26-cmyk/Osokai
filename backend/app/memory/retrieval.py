"""Unified retrieval: one query across facts, people, places, episodes.
Salience + recency ranked. This replaces keyword-only recall for the planner."""
import time as _time
try:
    from memory.store import db
except ImportError:
    from app.memory.store import db


def recall_all(query: str = "", k: int = 8):
    terms = [t for t in (query or "").lower().split() if len(t) > 2]
    out = []

    def _score(text: str, base: float, ts: float) -> float:
        tl = (text or "").lower()
        hits = sum(1.0 for t in terms if t in tl)
        if terms and not hits:
            return -1
        age_days = max(0, (_time.time() - (ts or 0)) / 86400)
        return base + hits * 2.0 - min(1.0, age_days / 90)

    try:
        for r in db().execute("SELECT id, fact, salience, ts FROM facts ORDER BY ts DESC LIMIT 100").fetchall():
            s = _score(r[1], r[2], r[3])
            if s >= 0:
                out.append((s, {"kind": "fact", "text": r[1], "ts": r[3]}))
    except Exception:
        pass
    try:
        for r in db().execute("SELECT id, name, relation, notes FROM mem_people ORDER BY id DESC LIMIT 100").fetchall():
            s = _score(f"{r[1]} {r[2]} {r[3]}", 2.0, 0)
            if s >= 0:
                out.append((s, {"kind": "person", "text": f"{r[1]} ({r[2]}): {r[3]}".strip(), "ts": 0}))
    except Exception:
        pass
    try:
        for r in db().execute("SELECT id, name, kind, notes FROM mem_places ORDER BY id DESC LIMIT 100").fetchall():
            s = _score(f"{r[1]} {r[2]} {r[3]}", 1.5, 0)
            if s >= 0:
                out.append((s, {"kind": "place", "text": f"{r[1]} ({r[2]}): {r[3]}".strip(), "ts": 0}))
    except Exception:
        pass
    try:
        for r in db().execute("SELECT id, text, importance, ts FROM mem_episodes ORDER BY ts DESC LIMIT 100").fetchall():
            s = _score(r[1], r[2], r[3])
            if s >= 0:
                out.append((s, {"kind": "episode", "text": r[1], "ts": r[3]}))
    except Exception:
        pass
    out.sort(key=lambda x: -x[0])
    return [o[1] for o in out[:max(1, min(30, k))]]
