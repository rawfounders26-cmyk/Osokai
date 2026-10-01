"""Local calendar — works TODAY without OAuth. Google Calendar sync plugs in later.
Chat: 'add dentist tomorrow 5pm', 'what's on today', 'cancel dentist'."""
import datetime
import re
import sqlite3
import os
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

def _db():
    db = _hardb(os.path.normpath(DB))
    db.execute("""CREATE TABLE IF NOT EXISTS cal_events(
        id INTEGER PRIMARY KEY, title TEXT, day TEXT, time TEXT,
        ts REAL, note TEXT, done INTEGER DEFAULT 0)""")
    return db

def add(title: str, day: str, time_: str = "", note: str = ""):
    db = _db()
    ts = _to_ts(day, time_)
    cur = db.execute("INSERT INTO cal_events(title, day, time, ts, note) VALUES(?,?,?,?,?)",
                     (title, day, time_, ts, note))
    db.commit()
    eid = cur.lastrowid
    try:
        from app.context.normalizers import calendar_created
    except ImportError:
        try:
            from context.normalizers import calendar_created
        except ImportError:
            calendar_created = lambda *a: None
    try:
        calendar_created(eid, title, day)
    except Exception:
        pass
    return {"ok": True, "id": eid, "when": f"{day} {time_}".strip()}

def list_all(day: str = ""):
    db = _db()
    q = "SELECT id, title, day, time, note FROM cal_events WHERE done=0"
    args = []
    if day:
        q += " AND day=?"
        args.append(day)
    q += " ORDER BY ts"
    return [{"id": r[0], "title": r[1], "day": r[2], "time": r[3], "note": r[4]}
            for r in db.execute(q, args)]

def cancel(eid_or_title):
    db = _db()
    try:
        db.execute("UPDATE cal_events SET done=1 WHERE id=?", (int(eid_or_title),))
    except (ValueError, TypeError):
        db.execute("UPDATE cal_events SET done=1 WHERE title LIKE ?", (f"%{eid_or_title}%",))
    db.commit()
    return {"ok": True}

def today_str():
    return datetime.date.today().isoformat()

def to_ics():
    """All undone events as ICS (Rencal-style portability: import into Google/Apple/Outlook)."""
    db = _db()
    rows = db.execute("SELECT id, title, day, time, ts, note FROM cal_events WHERE done=0 ORDER BY ts").fetchall()
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Osok-AI//Calendar//EN"]
    for i, title, day, tm, ts, note in rows:
        if not ts:
            continue
        dt = datetime.datetime.fromtimestamp(ts).strftime("%Y%m%dT%H%M%S")
        out += ["BEGIN:VEVENT", f"UID:osokai-{i}@Osok-AI", f"DTSTART:{dt}",
                f"SUMMARY:{title}", f"DESCRIPTION:{note or ''}", "END:VEVENT"]
    out.append("END:VCALENDAR")
    return "\r\n".join(out)

def _to_ts(day: str, time_: str) -> float:
    d = datetime.date.today()
    dl = day.lower()
    if dl in ("today", ""):
        pass
    elif dl == "tomorrow":
        d += datetime.timedelta(days=1)
    else:
        for i, name in enumerate(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
            if dl.startswith(name[:3]):
                delta = (i - d.weekday()) % 7 or 7
                d += datetime.timedelta(days=delta)
                break
        else:
            try:
                d = datetime.date.fromisoformat(day)
            except Exception:
                pass
    hh, mm = 9, 0
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", (time_ or "").lower())
    if m:
        hh, mm = int(m.group(1)), int(m.group(2) or 0)
        if m.group(3) == "pm" and hh < 12:
            hh += 12
    return datetime.datetime(d.year, d.month, d.day, hh, mm).timestamp()

def parse_add(text: str):
    """'add dentist tomorrow 5pm' -> (title, day, time). None if not an add."""
    m = re.match(r"^add\s+(.+?)(?:\s+(today|tomorrow|mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?))?(?:\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?))?$", text.strip(), re.I)
    if not m:
        return None
    return m.group(1).strip(), (m.group(2) or "today").lower(), (m.group(3) or "").lower()
