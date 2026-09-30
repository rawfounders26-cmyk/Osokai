"""Multi-agent orchestration — planner → executor → critic.

Goals used to compile once and sit still. Now one `auto_step(gid)` call:
1. planner picks the next actionable task (first todo leaf, shallowest first)
2. executor runs it through the existing tool loop (`run_task`)
3. critic (LLM judge, fail-open) accepts the result or requeues with a note
The proactive engine + Goals UI can drive this on a timer for fully
autonomous goal pursuit with the human watching, not babysitting.
"""
import os
import sqlite3

try:
    from app.paths import data as _pdata
except ImportError:
    from paths import data as _pdata

DB = _pdata("osokai.db")
MAX_AUTO_STEPS = 25  # safety cap per goal per day


def _db():
    return sqlite3.connect(os.path.normpath(DB), check_same_thread=False)


def _steps_today(gid: int) -> int:
    db = _db()
    try:
        lo = __import__("datetime").datetime.now().replace(hour=0, minute=0, second=0).timestamp()
        return db.execute("SELECT COUNT(*) FROM orch_log WHERE gid=? AND ts>=?", (gid, lo)).fetchone()[0]
    except Exception:
        return 0


def _log(gid: int, tid: int, verdict: str, note: str = ""):
    import time
    db = _db()
    try:
        db.execute("CREATE TABLE IF NOT EXISTS orch_log(id INTEGER PRIMARY KEY, gid INT, tid INT, verdict TEXT, note TEXT, ts REAL)")
        db.execute("INSERT INTO orch_log(gid, tid, verdict, note, ts) VALUES(?,?,?,?,?)",
                   (gid, tid, verdict, note[:1000], time.time()))
        db.commit()
    except Exception:
        pass


def _next_task(gid: int):
    """Shallowest todo leaf: earliest objective/project position first."""
    db = _db()
    r = db.execute(
        """SELECT t.id, t.title, t.kind FROM gtasks t
           JOIN projects p ON p.id=t.pid JOIN objectives o ON o.id=p.oid
           WHERE o.gid=? AND t.status IN ('todo','failed')
           ORDER BY o.pos, p.pos, t.pos LIMIT 1""", (gid,)).fetchone()
    return {"id": r[0], "title": r[1], "kind": r[2]} if r else None


def _critic(task_title: str, result: str) -> dict:
    """LLM judge. Fail-open: any error/ambiguity counts as accepted."""
    try:
        try:
            from app.grok_client import chat_with_grok
        except ImportError:
            from grok_client import chat_with_grok
        raw = chat_with_grok(
            "You review an AI agent's task result. Task: " + task_title +
            "\nResult (may be truncated): " + (result or "")[:1500] +
            "\nReply with exactly one word first: ACCEPT or REDO. "
            "REDO only if the result is empty, off-topic, or an error. Then one short sentence.")
    except Exception:
        return {"verdict": "accept", "note": "critic offline — fail-open"}
    up = (raw or "").strip().upper()
    if up.startswith("REDO"):
        return {"verdict": "redo", "note": (raw or "")[:300]}
    return {"verdict": "accept", "note": (raw or "")[:300]}


def auto_step(gid: int, device: str = "orchestrator") -> dict:
    """Execute + critique exactly one task of goal `gid`."""
    try:
        try:
            from app import goaltrees as _gt
        except ImportError:
            import goaltrees as _gt
    except Exception as e:
        return {"ok": False, "error": f"no goal engine: {e}"}
    if _steps_today(gid) >= MAX_AUTO_STEPS:
        return {"ok": False, "error": "daily auto-step cap reached — human check-in needed"}
    try:
        try:
            from app.usage import budget_ok
        except ImportError:
            from usage import budget_ok
        if not budget_ok():
            return {"ok": False, "error": "monthly AI budget reached — raise the cap to continue autonomous work"}
    except Exception:
        pass
    tree = _gt.get_tree(gid)
    if not tree:
        return {"ok": False, "error": "goal not found"}
    nxt = _next_task(gid)
    if not nxt:
        return {"ok": True, "done": True, "reply": f"Goal '{tree['title']}' — all tasks complete."}
    if nxt["kind"] in ("approval", "human"):
        return {"ok": True, "waiting": True,
                "reply": f"Paused for you: '{nxt['title']}' needs a human (approval or real-world action)."}
    if nxt["kind"] == "wait":
        _gt.set_task(nxt["id"], "doing", "watched by orchestrator")
        _log(gid, nxt["id"], "wait")
        return {"ok": True, "reply": f"Watching: '{nxt['title']}'."}
    out = _gt.run_task(nxt["id"], device)
    result = (out.get("result") or "") if isinstance(out, dict) else ""
    c = _critic(nxt["title"], result)
    if c["verdict"] == "redo":
        _gt.set_task(nxt["id"], "todo", "critic redo: " + c["note"])
        _log(gid, nxt["id"], "redo", c["note"])
        return {"ok": True, "redone": True,
                "reply": f"Task '{nxt['title']}' didn't pass review — requeued with feedback."}
    _log(gid, nxt["id"], "accept", c["note"])
    left = len([1 for o in (_gt.get_tree(gid) or {}).get("objectives", [])
                for p in o["projects"] for t in p["tasks"] if t["status"] in ("todo", "failed")])
    return {"ok": True, "task": nxt["title"], "tasks_left": left,
            "reply": f"Done: '{nxt['title']}' ✓ ({left} left in '{tree['title']}')."}


def history(gid: int, limit: int = 20):
    db = _db()
    try:
        rows = db.execute("SELECT tid, verdict, note, ts FROM orch_log WHERE gid=? ORDER BY ts DESC LIMIT ?",
                          (gid, limit)).fetchall()
        return [{"task_id": r[0], "verdict": r[1], "note": r[2], "ts": r[3]} for r in rows]
    except Exception:
        return []
