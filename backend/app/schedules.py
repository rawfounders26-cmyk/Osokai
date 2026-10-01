"""Scheduled autonomy — cron-style jobs for a self-driving agent.

Jobs (daily HH:MM or every-N-minutes): goal auto-steps, compiled briefings,
research sweeps, nudge scans. A 30s scheduler coroutine runs due jobs in
worker threads, logs every run, and pushes hub updates. The phone stays
in the pocket; the work still happens.
"""
import asyncio
import datetime
import json
import os
import sqlite3
import time

try:
    from app.paths import data as _pdata
except ImportError:
    from paths import data as _pdata

try:
    from app.db import connect as _hardb
except ImportError:
    from db import connect as _hardb
DB = _pdata("osokai.db")
KINDS = ("goal_step", "briefing", "research_sweep", "nudge_scan", "bills_recurring", "settle_reminder",
         "research_digest", "memory_consolidate")


def _db():
    db = _hardb(os.path.normpath(DB))
    db.execute("""CREATE TABLE IF NOT EXISTS schedules(
        id INTEGER PRIMARY KEY, name TEXT, kind TEXT, args TEXT,
        at_time TEXT DEFAULT '', every_min INT DEFAULT 0,
        enabled INTEGER DEFAULT 1, last_run REAL DEFAULT 0, created REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS schedule_runs(
        id INTEGER PRIMARY KEY, job INT, ok INT, note TEXT, ts REAL)""")
    return db


def create(name: str, kind: str, args: dict = None, at_time: str = "", every_min: int = 0) -> dict:
    if kind not in KINDS:
        return {"ok": False, "error": f"kind must be one of {KINDS}"}
    if not at_time and not every_min:
        return {"ok": False, "error": "give at_time (HH:MM) or every_min"}
    db = _db()
    cur = db.execute("INSERT INTO schedules(name, kind, args, at_time, every_min, created) VALUES(?,?,?,?,?,?)",
                     (name[:120], kind, json.dumps(args or {})[:2000], at_time, max(0, every_min), time.time()))
    db.commit()
    return {"ok": True, "id": cur.lastrowid}


def list_jobs():
    db = _db()
    rows = db.execute("SELECT id, name, kind, args, at_time, every_min, enabled, last_run FROM schedules ORDER BY id").fetchall()
    return [{"id": r[0], "name": r[1], "kind": r[2], "args": json.loads(r[3] or "{}"),
             "at_time": r[4], "every_min": r[5], "enabled": bool(r[6]), "last_run": r[7]} for r in rows]


def set_enabled(jid: int, enabled: bool) -> dict:
    db = _db()
    db.execute("UPDATE schedules SET enabled=? WHERE id=?", (1 if enabled else 0, jid))
    db.commit()
    return {"ok": True}


def remove(jid: int) -> dict:
    db = _db()
    db.execute("DELETE FROM schedules WHERE id=?", (jid,))
    db.commit()
    return {"ok": True}


def runs(jid: int = 0, limit: int = 20):
    db = _db()
    q = "SELECT id, job, ok, note, ts FROM schedule_runs"
    args: tuple = ()
    if jid:
        q += " WHERE job=?"
        args = (jid,)
    q += " ORDER BY id DESC LIMIT ?"
    rows = db.execute(q, args + (limit,)).fetchall()
    return [{"id": r[0], "job": r[1], "ok": bool(r[2]), "note": r[3], "ts": r[4]} for r in rows]


def _log_run(jid: int, ok: bool, note: str):
    db = _db()
    db.execute("INSERT INTO schedule_runs(job, ok, note, ts) VALUES(?,?,?,?)", (jid, 1 if ok else 0, note[:500], time.time()))
    db.execute("UPDATE schedules SET last_run=? WHERE id=?", (time.time(), jid))
    db.commit()


def _due(job: dict, now: float) -> bool:
    if job["last_run"] and now - job["last_run"] < 60:
        return False
    if job["every_min"]:
        base = job["last_run"] or job.get("created", now)
        return now - base >= job["every_min"] * 60
    if job["at_time"]:
        try:
            hh, mm = int(job["at_time"][:2]), int(job["at_time"][3:5])
        except Exception:
            return False
        dt = datetime.datetime.now()
        if dt.hour == hh and dt.minute == mm:
            day = dt.date().isoformat()
            if not job["last_run"] or datetime.datetime.fromtimestamp(job["last_run"]).date().isoformat() != day:
                return True
    return False


def execute(job: dict) -> dict:
    """Run one job synchronously. Never raises — returns ok/note."""
    kind, args = job["kind"], job.get("args", {})
    try:
        if kind == "goal_step":
            try:
                from app.orchestrator import auto_step
            except ImportError:
                from orchestrator import auto_step
            r = auto_step(int(args.get("gid", 0)), "scheduler")
            return {"ok": bool(r.get("ok")), "note": r.get("reply") or r.get("error", "?")}
        if kind == "briefing":
            try:
                from app.proactive import _push_briefing
            except ImportError:
                from proactive import _push_briefing
            return {"ok": True, "note": "briefing pushed" if _push_briefing() else "briefing already sent"}
        if kind == "research_sweep":
            try:
                from app.research import deep_research
            except ImportError:
                from research import deep_research
            fp = deep_research(args.get("topic", ""), min(2, int(args.get("depth", 1))))
            import os as _os
            return {"ok": True, "note": f"sweep saved: {_os.path.basename(fp)}"}
        if kind == "nudge_scan":
            try:
                from app.proactive import _tick
            except ImportError:
                from proactive import _tick
            return {"ok": True, "note": f"{_tick()} nudge(s)"}
        if kind == "bills_recurring":
            try:
                from app.bills import post_due_recurring
            except ImportError:
                from bills import post_due_recurring
            r = post_due_recurring()
            return {"ok": True, "note": f"posted: {', '.join(r['posted']) or 'none due'}"}
        if kind == "settle_reminder":
            try:
                from app.bills import settle_up, find_group, list_groups
                from app.proactive import nudge
            except ImportError:
                from bills import settle_up, find_group, list_groups
                from proactive import nudge
            g = find_group(args.get("group", "")) if args.get("group") else (list_groups()[:1] or [None])[0]
            if not g:
                return {"ok": False, "note": "no bill group"}
            s = settle_up(g["id"])
            if s["debts"] and nudge("settle", f"settle:{g['id']}", f"{g['name']}: " + s["reply"][:300]):
                return {"ok": True, "note": f"reminded {g['name']}"}
            return {"ok": True, "note": "all settled"}
        if kind == "research_digest":
            try:
                from app.digest import run_digest, run_all
            except ImportError:
                from digest import run_digest, run_all
            if args.get("topic"):
                r = run_digest(args["topic"])
                return {"ok": r["ok"], "note": r["note"]}
            r = run_all()
            return {"ok": True, "note": r["note"]}
        if kind == "memory_consolidate":
            try:
                from app.memory.consolidation import run as _con
            except ImportError:
                from memory.consolidation import run as _con
            r = _con()
            return {"ok": True,
                    "note": f"{r['episodes']} episodes, {r['decayed']} decayed, {r['pruned']} pruned"}
    except Exception as e:
        return {"ok": False, "note": f"{type(e).__name__}: {e}"[:300]}
    return {"ok": False, "note": "unknown kind"}


async def loop():
    """Scheduler coroutine — start beside the proactive loop."""
    await asyncio.sleep(15)
    while True:
        try:
            now = time.time()
            for job in [j for j in await asyncio.to_thread(list_jobs) if j["enabled"]]:
                if _due(job, now):
                    res = await asyncio.to_thread(execute, job)
                    await asyncio.to_thread(_log_run, job["id"], res["ok"], res["note"])
                    try:
                        try:
                            from app.main import hub
                        except ImportError:
                            from main import hub
                        await hub.push()
                    except Exception:
                        pass
            try:
                from app.specialists import tick as _spec_tick
            except ImportError:
                from specialists import tick as _spec_tick
            if await asyncio.to_thread(_spec_tick):
                try:
                    try:
                        from app.main import hub
                    except ImportError:
                        from main import hub
                    await hub.push()
                except Exception:
                    pass
        except Exception:
            pass
        await asyncio.sleep(30)
