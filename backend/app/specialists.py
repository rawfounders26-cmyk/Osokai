"""Persistent specialists — named autonomous workers with identity.

A specialist = persona (who it is) + skill + trigger (schedule and/or wake
event) + job (scheduler kind). Unlike one-shot agent runs, specialists persist:
they keep their name, accumulate run history, and fire on their own — Researcher
watches topics, Watcher watches stalled goals, Scheduler compiles briefings.
Event-triggered execution, not expensive continuous inference.
"""
import json
import time

try:
    from app.db import connect as _hardb
    from app.paths import data as _pdata
except ImportError:
    from db import connect as _hardb
    from paths import data as _pdata

import os as _os
DB = _pdata("osokai.db")

SEEDS = [
    {"name": "Researcher", "persona": "Watches the user's digest topics and compiles nightly sweeps with citations.",
     "skill": "deep-research", "kind": "research_digest", "args": {}, "every_min": 1440,
     "wake_event": "", "wake_match": {}},
    {"name": "Watcher", "persona": "Watches for stalled goals and nudges with the next concrete step.",
     "skill": "ecc-verification-loop", "kind": "nudge_scan", "args": {}, "every_min": 120,
     "wake_event": "goal.stalled", "wake_match": {}},
    {"name": "Scheduler", "persona": "Compiles the morning briefing and keeps the day's plan in view.",
     "skill": "prepare-for-calls", "kind": "briefing", "args": {}, "every_min": 0,
     "wake_event": "", "wake_match": {}, "at_time": "08:00"},
]


def _db():
    db = _hardb(_os.path.normpath(DB))
    db.execute("""CREATE TABLE IF NOT EXISTS specialists(
        id INTEGER PRIMARY KEY, name TEXT, persona TEXT, skill TEXT,
        kind TEXT, args TEXT DEFAULT '{}', every_min INT DEFAULT 0, at_time TEXT DEFAULT '',
        wake_event TEXT DEFAULT '', wake_match TEXT DEFAULT '{}',
        wake_cid INT DEFAULT 0, active INT DEFAULT 1, last_run REAL DEFAULT 0, ts REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS specialist_runs(
        id INTEGER PRIMARY KEY, sid INT, ok INT, note TEXT, ts REAL)""")
    return db


def _row(r):
    try:
        args, wm = json.loads(r[5] or "{}"), json.loads(r[8] or "{}")
    except Exception:
        args, wm = {}, {}
    return {"id": r[0], "name": r[1], "persona": r[2], "skill": r[3], "kind": r[4],
            "args": args, "every_min": r[6], "at_time": r[7], "wake_event": r[8],
            "wake_match": wm, "wake_cid": r[10], "active": bool(r[11]), "last_run": r[12]}


def create(name: str, persona: str = "", skill: str = "", kind: str = "nudge_scan",
           args: dict = None, every_min: int = 0, at_time: str = "",
           wake_event: str = "", wake_match: dict = None) -> dict:
    try:
        from app.schedules import KINDS
    except ImportError:
        from schedules import KINDS
    if kind not in KINDS:
        return {"ok": False, "error": f"kind must be one of {KINDS}"}
    if not (name or "").strip():
        return {"ok": False, "error": "name required"}
    if wake_event:
        try:
            from app.context.events import TYPES
        except ImportError:
            from context.events import TYPES
        if wake_event not in TYPES:
            return {"ok": False, "error": f"unknown event '{wake_event}'"}
    try:
        ablob, wblob = json.dumps(args or {}), json.dumps(wake_match or {})
        json.loads(ablob)
        json.loads(wblob)
    except Exception:
        return {"ok": False, "error": "args/match must be JSON"}
    db = _db()
    cur = db.execute("INSERT INTO specialists(name, persona, skill, kind, args, every_min, at_time, wake_event, wake_match, ts) VALUES(?,?,?,?,?,?,?,?,?,?)",
                     (name[:80], persona[:500], skill[:80], kind, ablob, max(0, every_min),
                      at_time, wake_event, wblob, time.time()))
    sid = cur.lastrowid
    db.commit()
    cid = 0
    if wake_event:
        try:
            from app.context.wake import add as _wadd
        except ImportError:
            from context.wake import add as _wadd
        w = _wadd(f"specialist:{name}", wake_event, "schedule",
                  wake_match or {}, {"job": kind, "job_args": args or {}})
        if w.get("ok"):
            cid = w["id"]
            db.execute("UPDATE specialists SET wake_cid=? WHERE id=?", (cid, sid))
            db.commit()
    return {"ok": True, "id": sid, "wake_condition": cid}


def list_specialists():
    db = _db()
    return [_row(r) for r in db.execute(
        "SELECT id, name, persona, skill, kind, args, every_min, at_time, wake_event, wake_match, wake_cid, active, last_run, ts FROM specialists ORDER BY id").fetchall()]


def set_active(sid: int, active: bool) -> dict:
    db = _db()
    db.execute("UPDATE specialists SET active=? WHERE id=?", (1 if active else 0, sid))
    db.commit()
    return {"ok": True}


def remove(sid: int) -> dict:
    db = _db()
    r = db.execute("SELECT wake_cid FROM specialists WHERE id=?", (sid,)).fetchone()
    db.execute("DELETE FROM specialists WHERE id=?", (sid,))
    db.execute("DELETE FROM specialist_runs WHERE sid=?", (sid,))
    db.commit()
    if r and r[0]:
        try:
            from app.context.wake import remove as _wdel
        except ImportError:
            from context.wake import remove as _wdel
        try:
            _wdel(r[0])
        except Exception:
            pass
    return {"ok": True}


def runs(sid: int = 0, limit: int = 20):
    db = _db()
    q = "SELECT id, sid, ok, note, ts FROM specialist_runs"
    args: tuple = ()
    if sid:
        q += " WHERE sid=?"
        args = (sid,)
    q += " ORDER BY id DESC LIMIT ?"
    return [{"id": r[0], "specialist": r[1], "ok": bool(r[2]), "note": r[3], "ts": r[4]}
            for r in db.execute(q, args + (max(1, min(50, limit)),)).fetchall()]


def _log(sid: int, ok: bool, note: str):
    db = _db()
    db.execute("INSERT INTO specialist_runs(sid, ok, note, ts) VALUES(?,?,?,?)",
               (sid, 1 if ok else 0, note[:500], time.time()))
    db.execute("UPDATE specialists SET last_run=? WHERE id=?", (time.time(), sid))
    db.commit()


def run_now(sid: int) -> dict:
    """Execute one specialist job now with persona context. Never raises."""
    db = _db()
    r = db.execute("SELECT id, name, persona, skill, kind, args FROM specialists WHERE id=? AND active=1",
                   (sid,)).fetchone()
    if not r:
        return {"ok": False, "error": "no such active specialist"}
    try:
        try:
            from app.schedules import execute as _exec
        except ImportError:
            from schedules import execute as _exec
        try:
            args = json.loads(r[5] or "{}")
        except Exception:
            args = {}
        out = _exec({"kind": r[4], "args": args})
        note = f"{r[1]} ({r[3]}): {out.get('note', '')}"[:400]
        _log(sid, out.get("ok", False), note)
        try:
            from app.proactive import nudge
        except ImportError:
            from proactive import nudge
        nudge("specialist", f"spec:{sid}:{int(time.time() // 3600)}",
              f"🤖 {r[1]}: {out.get('note', '')[:250]}")
        return {"ok": out.get("ok", False), "note": note}
    except Exception as e:
        _log(sid, False, f"{type(e).__name__}: {e}"[:300])
        return {"ok": False, "error": f"{type(e).__name__}: {e}"[:200]}


def tick() -> int:
    """Due-check for interval/at-time specialists. Called from the scheduler loop."""
    import datetime as _dt
    now = time.time()
    fired = 0
    try:
        for s in [x for x in list_specialists() if x["active"]]:
            due = False
            if s["every_min"] and now - (s["last_run"] or 0) >= s["every_min"] * 60:
                due = True
            elif s["at_time"]:
                try:
                    hh, mm = int(s["at_time"][:2]), int(s["at_time"][3:5])
                    dt = _dt.datetime.now()
                    if dt.hour == hh and dt.minute == mm and (
                            not s["last_run"] or _dt.datetime.fromtimestamp(s["last_run"]).date() != dt.date()):
                        due = True
                except Exception:
                    pass
            if due:
                run_now(s["id"])
                fired += 1
    except Exception:
        pass
    return fired


def seed() -> dict:
    existing = {s["name"] for s in list_specialists()}
    made = []
    for s in SEEDS:
        if s["name"] not in existing:
            r = create(s["name"], s["persona"], s["skill"], s["kind"], s["args"],
                       s["every_min"], s.get("at_time", ""), s["wake_event"], s["wake_match"])
            if r.get("ok"):
                made.append(s["name"])
    return {"ok": True, "seeded": made}
