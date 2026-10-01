"""Wake conditions — event-driven autonomy, not just timers.

Conditions (stored, user-togglable): WHEN <event> + optional match → THEN nudge /
open loop / run schedule. check() runs inside the proactive tick: finds fresh
unconsumed events, fires matching conditions once each, records consumption so
nothing double-fires across restarts.
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

ACTIONS = ("nudge", "loop", "schedule")


def _db():
    db = _hardb(_os.path.normpath(DB))
    db.execute("""CREATE TABLE IF NOT EXISTS wake_conditions(
        id INTEGER PRIMARY KEY, name TEXT, event TEXT, match TEXT DEFAULT '{}',
        action TEXT, args TEXT DEFAULT '{}', enabled INT DEFAULT 1, ts REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS wake_fired(
        cond INT, event_id INT, ts REAL, PRIMARY KEY(cond, event_id))""")
    return db


def add(name: str, event: str, action: str, match: dict = None, args: dict = None) -> dict:
    try:
        from app.context.events import TYPES
    except ImportError:
        from context.events import TYPES
    if event not in TYPES:
        return {"ok": False, "error": f"unknown event '{event}'"}
    if action not in ACTIONS:
        return {"ok": False, "error": f"action must be one of {ACTIONS}"}
    try:
        mblob, ablob = json.dumps(match or {}), json.dumps(args or {})
        json.loads(mblob)
        json.loads(ablob)
    except Exception:
        return {"ok": False, "error": "match/args must be JSON"}
    db = _db()
    cur = db.execute("INSERT INTO wake_conditions(name, event, match, action, args, ts) VALUES(?,?,?,?,?,?)",
                     (name[:120], event, mblob, action, ablob, time.time()))
    db.commit()
    return {"ok": True, "id": cur.lastrowid}


def list_conditions():
    rows = _db().execute("SELECT id, name, event, match, action, args, enabled FROM wake_conditions ORDER BY id").fetchall()
    out = []
    for r in rows:
        try:
            m, a = json.loads(r[3] or "{}"), json.loads(r[5] or "{}")
        except Exception:
            m, a = {}, {}
        out.append({"id": r[0], "name": r[1], "event": r[2], "match": m,
                    "action": r[4], "args": a, "enabled": bool(r[6])})
    return out


def set_enabled(cid: int, enabled: bool) -> dict:
    db = _db()
    db.execute("UPDATE wake_conditions SET enabled=? WHERE id=?", (1 if enabled else 0, cid))
    db.commit()
    return {"ok": True}


def remove(cid: int) -> dict:
    db = _db()
    db.execute("DELETE FROM wake_conditions WHERE id=?", (cid,))
    db.commit()
    return {"ok": True}


def _matches(cond_match: dict, payload: dict) -> bool:
    for k, v in cond_match.items():
        pv = payload.get(k, "")
        if isinstance(v, str):
            if v.lower() not in str(pv).lower():
                return False
        elif pv != v:
            return False
    return True


def check() -> list:
    """Fire enabled conditions against fresh events. Returns fired descriptions. Never raises."""
    fired = []
    try:
        try:
            from app.context.events import list_events
        except ImportError:
            from context.events import list_events
        conds = [c for c in list_conditions() if c["enabled"]]
        if not conds:
            return fired
        by_type: dict = {}
        for c in conds:
            by_type.setdefault(c["event"], []).append(c)
        for etype, clist in by_type.items():
            for ev in list_events(etype, since=time.time() - 86400, limit=50):
                for c in clist:
                    db = _db()
                    if db.execute("SELECT 1 FROM wake_fired WHERE cond=? AND event_id=?",
                                  (c["id"], ev["id"])).fetchone():
                        continue
                    if not _matches(c["match"], ev["payload"]):
                        continue
                    ok = _fire(c, ev)
                    db.execute("INSERT OR IGNORE INTO wake_fired(cond, event_id, ts) VALUES(?,?,?)",
                               (c["id"], ev["id"], time.time()))
                    db.commit()
                    fired.append(f"{c['name']}: {'fired' if ok else 'failed'}")
    except Exception:
        pass
    return fired


def _fire(cond: dict, ev: dict) -> bool:
    try:
        action, args = cond["action"], cond["args"]
        if action == "nudge":
            try:
                from app.proactive import nudge
            except ImportError:
                from proactive import nudge
            nudge("wake", f"wake:{cond['id']}:{ev['id']}",
                  args.get("text", f"{cond['name']}: {ev['type']}")[:400])
            return True
        if action == "loop":
            try:
                from app.loops import add as _add
            except ImportError:
                from loops import add as _add
            _add("promise", args.get("title", cond["name"])[:200], "wake")
            return True
        if action == "schedule":
            try:
                from app.schedules import execute as _exec
            except ImportError:
                from schedules import execute as _exec
            r = _exec({"kind": args.get("job", "nudge_scan"), "args": args.get("job_args", {})})
            return bool(r.get("ok"))
    except Exception:
        pass
    return False
