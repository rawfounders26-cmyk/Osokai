"""Semantic memory: people the user knows. Who + relation + what matters."""
try:
    from memory.store import db, now
except ImportError:
    from app.memory.store import db, now


def remember_person(name: str, relation: str = "", notes: str = "") -> dict:
    name = (name or "").strip()[:120]
    if not name:
        return {"ok": False, "error": "name required"}
    conn = db()
    row = conn.execute("SELECT id FROM mem_people WHERE lower(name)=lower(?)", (name,)).fetchone()
    if row:
        conn.execute("UPDATE mem_people SET relation=?, notes=?, ts=? WHERE id=?",
                     (relation[:80], notes[:500], now(), row[0]))
        conn.commit()
        return {"ok": True, "id": row[0], "updated": True}
    cur = conn.execute("INSERT INTO mem_people(name, relation, notes, ts) VALUES(?,?,?,?)",
                       (name, relation[:80], notes[:500], now()))
    conn.commit()
    return {"ok": True, "id": cur.lastrowid}


def list_people():
    return [{"id": r[0], "name": r[1], "relation": r[2], "notes": r[3]}
            for r in db().execute("SELECT id, name, relation, notes FROM mem_people ORDER BY name").fetchall()]


def find_person(query: str):
    q = f"%{(query or '').strip().lower()}%"
    if len(q) <= 2:
        return []
    return [{"id": r[0], "name": r[1], "relation": r[2], "notes": r[3]} for r in db().execute(
        "SELECT id, name, relation, notes FROM mem_people WHERE lower(name) LIKE ? OR lower(notes) LIKE ?",
        (q, q)).fetchall()]
