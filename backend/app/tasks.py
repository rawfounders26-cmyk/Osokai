"""Durable task runs — every complex goal becomes a tracked run with receipts.
Survives restarts (SQLite), progress-updated, completable, retryable."""
import sqlite3, os, time, json

try:
    from app.paths import data as _pdata
except ImportError:
    from paths import data as _pdata

DB = _pdata("osokai.db")

def _db():
    db = sqlite3.connect(os.path.normpath(DB), check_same_thread=False)
    db.execute("""CREATE TABLE IF NOT EXISTS task_runs(
        id INTEGER PRIMARY KEY, title TEXT, kind TEXT, status TEXT,
        progress INTEGER DEFAULT 0, result TEXT DEFAULT '', steps TEXT DEFAULT '[]',
        created REAL, updated REAL)""")
    return db

def create(title: str, kind: str = "agent"):
    db = _db()
    now = time.time()
    cur = db.execute("INSERT INTO task_runs(title, kind, status, created, updated) VALUES(?,?,?,?,?)",
                     (title, kind, "running", now, now))
    db.commit()
    return cur.lastrowid

def log_step(rid: int, text: str, progress: int = 0):
    db = _db()
    r = db.execute("SELECT steps FROM task_runs WHERE id=?", (rid,)).fetchone()
    steps = json.loads(r[0]) if r and r[0] else []
    steps.append({"t": time.time(), "text": text[:500]})
    db.execute("UPDATE task_runs SET steps=?, progress=?, updated=? WHERE id=?",
               (json.dumps(steps[-50:]), progress, time.time(), rid))
    db.commit()

def complete(rid: int, result: str, status: str = "done"):
    db = _db()
    db.execute("UPDATE task_runs SET status=?, result=?, progress=?, updated=? WHERE id=?",
               (status, result[:4000], 100 if status == "done" else 0, time.time(), rid))
    db.commit()
    return get(rid)

def get(rid: int):
    db = _db()
    r = db.execute("SELECT id, title, kind, status, progress, result, steps, created, updated FROM task_runs WHERE id=?",
                   (rid,)).fetchone()
    if not r:
        return None
    return {"id": r[0], "title": r[1], "kind": r[2], "status": r[3], "progress": r[4],
            "result": r[5], "steps": json.loads(r[6] or "[]"), "created": r[7], "updated": r[8]}

def list_runs(limit: int = 20, status: str = ""):
    db = _db()
    q = "SELECT id, title, kind, status, progress, result, steps, created, updated FROM task_runs"
    args = []
    if status:
        q += " WHERE status=?"
        args.append(status)
    q += " ORDER BY updated DESC LIMIT ?"
    args.append(limit)
    return [{"id": r[0], "title": r[1], "kind": r[2], "status": r[3], "progress": r[4],
             "result": (r[5] or "")[:300], "steps": len(json.loads(r[6] or "[]")),
             "created": r[7], "updated": r[8]}
            for r in db.execute(q, args)]

def running():
    return list_runs(20, "running")

def retry(rid: int):
    """Re-queue a failed run: back to running, keeps old steps as history."""
    db = _db()
    db.execute("UPDATE task_runs SET status='running', progress=0, updated=? WHERE id=?", (time.time(), rid))
    db.commit()
    return get(rid)
