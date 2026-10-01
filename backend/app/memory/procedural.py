"""Procedural memory: how the user does things. Routines learned from repetition."""
import json as _json
try:
    from memory.store import db, now
except ImportError:
    from app.memory.store import db, now


def record_routine(name: str, steps: list) -> dict:
    name = (name or "").strip()[:120]
    if not name or not steps:
        return {"ok": False, "error": "name + steps required"}
    conn = db()
    row = conn.execute("SELECT id, times_used FROM mem_routines WHERE lower(name)=lower(?)", (name,)).fetchone()
    if row:
        conn.execute("UPDATE mem_routines SET steps=?, times_used=?, ts=? WHERE id=?",
                     (_json.dumps(steps)[:2000], row[1] + 1, now(), row[0]))
        conn.commit()
        return {"ok": True, "id": row[0], "times_used": row[1] + 1}
    cur = conn.execute("INSERT INTO mem_routines(name, steps, times_used, ts) VALUES(?,?,1,?)",
                       (name, _json.dumps(steps)[:2000], now()))
    conn.commit()
    return {"ok": True, "id": cur.lastrowid, "times_used": 1}


def list_routines():
    out = []
    for r in db().execute("SELECT id, name, steps, times_used FROM mem_routines ORDER BY times_used DESC").fetchall():
        try:
            steps = _json.loads(r[2] or "[]")
        except Exception:
            steps = []
        out.append({"id": r[0], "name": r[1], "steps": steps, "times_used": r[3]})
    return out


def suggest_routines(query: str):
    q = (query or "").lower()
    if not q:
        return []
    return [r for r in list_routines()
            if q in r["name"].lower() or any(q in str(s).lower() for s in r["steps"])][:3]
