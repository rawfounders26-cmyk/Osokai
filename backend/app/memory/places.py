"""Semantic memory: places (home, office, favorite spots). Where things happen."""
try:
    from memory.store import db, now
except ImportError:
    from app.memory.store import db, now


def remember_place(name: str, kind: str = "", notes: str = "") -> dict:
    name = (name or "").strip()[:120]
    if not name:
        return {"ok": False, "error": "name required"}
    conn = db()
    row = conn.execute("SELECT id FROM mem_places WHERE lower(name)=lower(?)", (name,)).fetchone()
    if row:
        conn.execute("UPDATE mem_places SET kind=?, notes=?, ts=? WHERE id=?",
                     (kind[:80], notes[:500], now(), row[0]))
        conn.commit()
        return {"ok": True, "id": row[0], "updated": True}
    cur = conn.execute("INSERT INTO mem_places(name, kind, notes, ts) VALUES(?,?,?,?)",
                       (name, kind[:80], notes[:500], now()))
    conn.commit()
    return {"ok": True, "id": cur.lastrowid}


def list_places():
    return [{"id": r[0], "name": r[1], "kind": r[2], "notes": r[3]}
            for r in db().execute("SELECT id, name, kind, notes FROM mem_places ORDER BY name").fetchall()]
