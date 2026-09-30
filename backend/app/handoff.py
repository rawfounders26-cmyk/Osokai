"""Cross-device handoff — start on desktop, continue on phone mid-step.

A handoff snapshots goal state (progress + next actionable task) and relays it
(sealed transport via relay-lite, or client-sealed e2e for paranoid mode).
Accepting on the target device marks it consumed and drops a resume nudge —
conflict-free because a handoff is single-accept with expiry.
"""
import json
import os
import sqlite3
import time

try:
    from app.paths import data as _pdata
except ImportError:
    from paths import data as _pdata

DB = _pdata("osokai.db")
TTL = 24 * 3600


def _db():
    db = sqlite3.connect(os.path.normpath(DB), check_same_thread=False)
    db.execute("""CREATE TABLE IF NOT EXISTS handoffs(
        id INTEGER PRIMARY KEY, gid INT, title TEXT, progress INT, next_task TEXT,
        from_device TEXT, to_device TEXT, status TEXT DEFAULT 'open', ts REAL, exp REAL)""")
    return db


def _snapshot(gid: int):
    try:
        try:
            from app import goaltrees as _gt
        except ImportError:
            import goaltrees as _gt
        t = _gt.get_tree(gid)
    except Exception:
        t = None
    if not t:
        return None
    nxt = ""
    for o in t["objectives"]:
        for p in o["projects"]:
            for task in p["tasks"]:
                if task["status"] in ("todo", "failed") and not nxt:
                    nxt = task["title"]
    return {"title": t["title"], "progress": t["progress"], "next_task": nxt}


def create(gid: int, from_device: str, to_device: str, sealed: dict = None) -> dict:
    snap = _snapshot(gid)
    if not snap:
        return {"ok": False, "error": "goal not found"}
    db = _db()
    cur = db.execute("INSERT INTO handoffs(gid, title, progress, next_task, from_device, to_device, ts, exp) VALUES(?,?,?,?,?,?,?,?)",
                     (gid, snap["title"], snap["progress"], snap["next_task"],
                      from_device[:80], to_device[:80], time.time(), time.time() + TTL))
    hid = cur.lastrowid
    db.commit()
    if sealed:
        try:
            try:
                from app.e2e import push_envelope
            except ImportError:
                from e2e import push_envelope
            push_envelope(to_device, sealed)
        except Exception:
            pass
    else:
        try:
            try:
                from app.relay import seal
            except ImportError:
                from relay import seal
            seal(to_device, {"kind": "handoff", "id": hid, "title": snap["title"],
                             "progress": snap["progress"], "next": snap["next_task"]})
        except Exception:
            pass
    return {"ok": True, "id": hid, **snap}


def pending(device: str):
    db = _db()
    db.execute("UPDATE handoffs SET status='expired' WHERE status='open' AND exp<?", (time.time(),))
    db.commit()
    rows = db.execute("SELECT id, gid, title, progress, next_task, from_device, ts FROM handoffs WHERE to_device=? AND status='open' ORDER BY id",
                      (device,)).fetchall()
    return [{"id": r[0], "gid": r[1], "title": r[2], "progress": r[3],
             "next_task": r[4], "from": r[5], "ts": r[6]} for r in rows]


def accept(hid: int, device: str) -> dict:
    db = _db()
    r = db.execute("SELECT gid, title, progress, to_device, status FROM handoffs WHERE id=?", (hid,)).fetchone()
    if not r:
        return {"ok": False, "error": "no such handoff"}
    if r[4] != "open":
        return {"ok": False, "error": f"already {r[4]} — single-accept, no conflicts"}
    if r[3] != device:
        return {"ok": False, "error": "not addressed to this device"}
    snap = _snapshot(r[0]) or {"title": r[1], "progress": r[2], "next_task": ""}
    db.execute("UPDATE handoffs SET status='accepted' WHERE id=?", (hid,))
    db.commit()
    try:
        try:
            from app.proactive import nudge
        except ImportError:
            from proactive import nudge
        nudge("handoff", f"handoff:{hid}",
              f"📲 Picked up '{snap['title']}' ({snap['progress']}%) — next: {snap['next_task'] or 'all done'}")
    except Exception:
        pass
    return {"ok": True, "gid": r[0], **snap,
            "resume": f"Continue '{snap['title']}': next up is '{snap['next_task']}'." if snap["next_task"] else "Goal complete — nothing to resume."}
