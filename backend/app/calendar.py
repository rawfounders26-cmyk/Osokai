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


def _span(ev: dict, default_min: int = 60):
    """(start_ts, end_ts) for an event; untimed = all-day busy is False."""
    import re as _re
    t = (ev.get("time") or "").strip().lower()
    m = _re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?(?:\s*[-–]\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?$", t)
    day = ev.get("day", "")
    try:
        base = datetime.date.fromisoformat(day) if day else datetime.date.today()
    except Exception:
        base = datetime.date.today()
    if not m:
        return None, None
    def _h(h, ap, dflt):
        h = int(h)
        ap = ap or dflt
        if ap == "pm" and h < 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
        return h
    h1 = _h(m.group(1), m.group(3), "am")
    mi1 = int(m.group(2) or 0)
    s = datetime.datetime(base.year, base.month, base.day, h1, mi1).timestamp()
    if m.group(4):
        h2 = _h(m.group(4), m.group(6), m.group(3) or "am")
        e = datetime.datetime(base.year, base.month, base.day, h2, int(m.group(5) or 0)).timestamp()
    else:
        e = s + default_min * 60
    return s, e


def free_slots(day: str = "", duration_min: int = 60, work_start: int = 8, work_end: int = 21):
    """Free windows on a day from local events. No cloud needed."""
    day = day or today_str()
    try:
        base = datetime.date.fromisoformat(day)
    except Exception:
        return {"ok": False, "error": "bad day (YYYY-MM-DD)"}
    busy = []
    for e in list_all(day):
        s, en = _span(e)
        if s:
            busy.append((s, en))
    busy.sort()
    lo = datetime.datetime(base.year, base.month, base.day, work_start).timestamp()
    hi = datetime.datetime(base.year, base.month, base.day, work_end).timestamp()
    need, out, cur = duration_min * 60, [], lo
    for s, e in busy:
        if s - cur >= need:
            out.append({"from": datetime.datetime.fromtimestamp(cur).strftime("%H:%M"),
                        "to": datetime.datetime.fromtimestamp(s).strftime("%H:%M")})
        cur = max(cur, e)
    if hi - cur >= need:
        out.append({"from": datetime.datetime.fromtimestamp(cur).strftime("%H:%M"),
                    "to": datetime.datetime.fromtimestamp(hi).strftime("%H:%M")})
    return {"ok": True, "day": day, "free": out}


def conflicts(title: str, day: str, time_: str = "") -> dict:
    """Would this event collide? Returns colliding events (empty = clear)."""
    s, e = _span({"title": title, "day": day, "time": time_})
    if not s:
        return {"ok": True, "conflicts": [], "note": "untimed — cannot collide"}
    hits = []
    for ev in list_all(day):
        s2, e2 = _span(ev)
        if s2 and s < e2 and s2 < e:
            hits.append({"id": ev.get("id"), "title": ev.get("title"), "time": ev.get("time")})
    return {"ok": True, "conflicts": hits}


def invite(title: str, day: str, time_: str = "", attendees: str = ""):
    """Create the event + draft attendee invites via the email outbox (approval-gated send)."""
    tos = [a.strip() for a in (attendees or "").replace(";", ",").split(",") if "@" in a]
    c = conflicts(title, day, time_)
    if c["conflicts"]:
        return {"ok": False, "error": "collides with: " + "; ".join(
            f"{e['title']} {e['time']}" for e in c["conflicts"]),
                "conflicts": c["conflicts"]}
    ev = add(title, day, time_)
    draft_ids = []
    if tos:
        try:
            from app.emailbox import compose
        except ImportError:
            from emailbox import compose
        for to in tos[:20]:
            d = compose(to, f"Invitation: {title}",
                        f"You are invited: {title} — {day} {time_}. (via Osok-AI; approve to send)")
            if d.get("ok"):
                draft_ids.append(d["id"])
    return {"ok": True, "event_id": ev.get("id"), "when": ev.get("when"),
            "invites_drafted": draft_ids}

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
