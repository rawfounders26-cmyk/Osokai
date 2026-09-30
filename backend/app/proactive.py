"""Proactive engine — Osok-AI acts without being asked.

A single asyncio loop (zero new deps) ticks every 60s and:
- nudges on due open-loops, aging approvals, stalled goals, money owed
- pushes the morning briefing once a day at 08:00 local
Nudges land in a local table + bump the sync hub so every surface refreshes.
"""
import asyncio
import datetime
import os
import sqlite3
import time

try:
    from app.paths import data as _pdata
except ImportError:
    from paths import data as _pdata

DB = _pdata("osokai.db")
BRIEF_HOUR = 8
DEDUP_WINDOW = 12 * 3600


def _db():
    db = sqlite3.connect(os.path.normpath(DB), check_same_thread=False)
    db.execute("""CREATE TABLE IF NOT EXISTS nudges(
        id INTEGER PRIMARY KEY, kind TEXT, key TEXT, text TEXT, ts REAL, seen INTEGER DEFAULT 0)""")
    return db


def nudge(kind: str, key: str, text: str) -> bool:
    """Store a nudge unless the same kind+key fired inside the dedup window."""
    db = _db()
    recent = db.execute("SELECT 1 FROM nudges WHERE kind=? AND key=? AND ts>?",
                        (kind, key, time.time() - DEDUP_WINDOW)).fetchone()
    if recent:
        return False
    db.execute("INSERT INTO nudges(kind, key, text, ts) VALUES(?,?,?,?)",
               (kind, key, text[:500], time.time()))
    db.commit()
    return True


def list_nudges(unseen_only: bool = True, limit: int = 30):
    db = _db()
    q = "SELECT id, kind, key, text, ts, seen FROM nudges"
    if unseen_only:
        q += " WHERE seen=0"
    q += " ORDER BY ts DESC LIMIT ?"
    rows = db.execute(q, (limit,)).fetchall()
    return [{"id": r[0], "kind": r[1], "key": r[2], "text": r[3], "ts": r[4], "seen": bool(r[5])}
            for r in rows]


def mark_seen(nid: int = 0):
    db = _db()
    if nid:
        db.execute("UPDATE nudges SET seen=1 WHERE id=?", (nid,))
    else:
        db.execute("UPDATE nudges SET seen=1 WHERE seen=0")
    db.commit()
    return {"ok": True}


def _tick() -> int:
    """One proactive pass. Returns number of new nudges. Never raises."""
    made = 0
    try:
        try:
            from app.loops import due_now
            from app.memory import Memory
        except ImportError:
            from loops import due_now
            from memory import Memory
        mem = Memory()
        for lp in due_now():
            if nudge("loop_due", f"loop:{lp.get('id')}", f"Reminder due: {lp.get('title', '')}"):
                made += 1
        for a in mem.approval_list_pending():
            age_min = (time.time() - (a.get("ts") or 0)) / 60
            if age_min >= 30 and nudge("approval_aging", f"appr:{a['id']}",
                                       f"Still waiting ({int(age_min)}m): {(a.get('message') or '')[:120]}"):
                made += 1
    except Exception:
        pass
    try:
        try:
            from app import goaltrees as _gt
        except ImportError:
            import goaltrees as _gt
        for g in _gt.list_trees():
            if g["progress"] == 0 and nudge("goal_stalled", f"goal:{g['id']}",
                                            f"Goal '{g['title']}' hasn't moved — run the next task?"):
                made += 1
    except Exception:
        pass
    try:
        try:
            from app.bills import list_groups
        except ImportError:
            from bills import list_groups
        owe = 0
        for g in list_groups():
            for d in g.get("balances", []):
                if d.get("from") == "Me":
                    owe += d.get("amount", 0)
        if owe and nudge("money", "money:" + datetime.date.today().isoformat(),
                         f"You owe ₹{owe} across bill splits — settle up?"):
            made += 1
    except Exception:
        pass
    return made


def _briefing_due() -> bool:
    db = _db()
    day = datetime.date.today().isoformat()
    return not db.execute("SELECT 1 FROM nudges WHERE kind='briefing' AND key=?", (day,)).fetchone()


def _push_briefing():
    try:
        try:
            from app.briefing import build
        except ImportError:
            from briefing import build
        b = build()
        text = b["title"] + " — " + " · ".join(b["lines"][:5])
        if nudge("briefing", datetime.date.today().isoformat(), text):
            return True
    except Exception:
        pass
    return False


async def loop():
    """Background task started on server startup. Survives individual failures."""
    await asyncio.sleep(10)
    while True:
        try:
            made = await asyncio.to_thread(_tick)
            now = datetime.datetime.now()
            if now.hour >= BRIEF_HOUR and _briefing_due():
                if await asyncio.to_thread(_push_briefing):
                    made += 1
            if made:
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
        await asyncio.sleep(60)
