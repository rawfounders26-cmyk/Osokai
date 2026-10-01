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

try:
    from app.db import connect as _hardb
except ImportError:
    from db import connect as _hardb
DB = _pdata("osokai.db")
MAX_AUTO_STEPS = 25  # safety cap per goal per day


def _db():
    return _hardb(os.path.normpath(DB))


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
    try:
        from app.goaltrees import _db as _gdb
    except ImportError:
        from goaltrees import _db as _gdb
    db = _gdb()
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
    # step 3: tasks WITH subtasks walk the verified path (propose -> execute ->
    # verify -> checkpoint). Tasks without subtasks keep the legacy whole-task run.
    all_subs = _gt.list_subtasks(nxt["id"])
    subs = [s for s in all_subs if s["status"] in ("todo", "failed")]
    if all_subs and not subs:
        _gt.set_task(nxt["id"], "done", "all subtasks verified")
        _log(gid, nxt["id"], "accept", "all subtasks verified")
        return {"ok": True, "task": nxt["title"],
                "reply": f"Task '{nxt['title']}' complete — all subtasks verified ✓"}
    if subs and nxt["kind"] in ("research", "create", "browse"):
        return _auto_substep(gid, tree, nxt, subs[0], device)
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


def _auto_substep(gid: int, tree: dict, task: dict, sub: dict, device: str) -> dict:
    """One verified subtask: propose actions, run each through execute+verify,
    checkpoint the subtask ONLY on verify-pass. Parent task completes when all
    subtasks are done — counted, not claimed."""
    try:
        try:
            from app.actions import propose
            from app.goaltrees import set_subtask, list_subtasks
            from app.verify import run_verified
        except ImportError:
            from actions import propose
            from goaltrees import set_subtask, list_subtasks
            from verify import run_verified
    except Exception as e:
        return {"ok": False, "error": f"no verify engine: {e}"}
    set_subtask(sub["id"], "doing")
    notes = []
    try:
        try:
            from app.policy.dispatch import request as _gate
        except ImportError:
            from policy.dispatch import request as _gate
    except Exception:
        _gate = lambda *a, **k: {"ok": True, "auto": True}
    for step in propose(sub["title"], task["kind"]):
        # fill blank args from subtask context where the mapping is unambiguous
        args = dict(step.get("args", {}))
        if step["action"] == "add_loop" and not args.get("title"):
            args["title"] = sub["title"][:200]
        if step["action"] == "web_search" and not args.get("query"):
            args["query"] = sub["title"][:200]
        if step["action"] == "notify_user" and not args.get("text"):
            args["text"] = sub["title"][:200]
        if step["action"] == "create_file" and not args.get("path"):
            slug = "".join(c if c.isalnum() else "-" for c in sub["title"].lower()).strip("-")[:40] or "note"
            args["path"] = f"{slug}.md"
            args["content"] = args.get("content", "") or f"# {sub['title']}\n"
        g = _gate(step["action"], args, device)
        if not g["ok"] and g.get("waiting"):
            set_subtask(sub["id"], "waiting", f"approval #{g['approval_id']}: {step['action']}")
            _log(gid, task["id"], "wait", f"{sub['title']} :: approval #{g['approval_id']}")
            return {"ok": True, "waiting": True, "approval_id": g["approval_id"],
                    "reply": g.get("reply", f"Paused for approval #{g['approval_id']}.")}
        if not g["ok"]:
            set_subtask(sub["id"], "todo", "dispatcher rejected: " + g.get("error", "?")[:300])
            _log(gid, task["id"], "redo", sub["title"] + " :: dispatcher rejection")
            return {"ok": True, "redone": True,
                    "reply": f"Subtask '{sub['title']}' rejected at the approval gate — requeued."}
        r = run_verified({"action": step["action"], "args": args}, device)
        notes.append(f"{step['action']}: {r['evidence'][:120]}")
        if r.get("waiting"):
            set_subtask(sub["id"], "waiting", r["evidence"][:500])
            _log(gid, task["id"], "wait", sub["title"])
            return {"ok": True, "waiting": True,
                    "reply": f"Paused for you on '{sub['title']}' ({r['evidence'][:150]})."}
        if not r["verified"]:
            set_subtask(sub["id"], "todo", "verify failed: " + r["evidence"][:400])
            _log(gid, task["id"], "redo", sub["title"] + " :: " + r["evidence"][:200])
            return {"ok": True, "redone": True,
                    "reply": f"Subtask '{sub['title']}' failed verification — requeued ({r['evidence'][:150]})."}
    set_subtask(sub["id"], "done", "; ".join(notes)[:1500])
    _log(gid, task["id"], "accept", sub["title"])
    remaining = [s for s in list_subtasks(task["id"]) if s["status"] in ("todo", "failed")]
    if not remaining:
        try:
            from app.goaltrees import set_task
        except ImportError:
            from goaltrees import set_task
        set_task(task["id"], "done", f"all {len(list_subtasks(task['id']))} subtasks verified")
    left_tasks = len([1 for o in tree.get("objectives", []) for p in o["projects"]
                      for t in p["tasks"] if t["status"] in ("todo", "failed")])
    return {"ok": True, "task": task["title"], "subtask": sub["title"], "tasks_left": left_tasks,
            "reply": f"Verified: '{sub['title']}' ✓ ({'; '.join(notes)[:150]})."}


def history(gid: int, limit: int = 20):
    db = _db()
    try:
        rows = db.execute("SELECT tid, verdict, note, ts FROM orch_log WHERE gid=? ORDER BY ts DESC LIMIT ?",
                          (gid, limit)).fetchall()
        return [{"task_id": r[0], "verdict": r[1], "note": r[2], "ts": r[3]} for r in rows]
    except Exception:
        return []
