"""Goals — recurring watches (page change, text availability, price threshold).
Background checker dedups alerts; bell + WS pick them up like notifications."""
import hashlib, os, re, sqlite3, threading, time

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
    db.execute("""CREATE TABLE IF NOT EXISTS goals(
        id INTEGER PRIMARY KEY, title TEXT, url TEXT, kind TEXT, target TEXT,
        last_value TEXT, active INTEGER, created REAL, last_check REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS goal_alerts(
        id INTEGER PRIMARY KEY, gid INTEGER, text TEXT, ts REAL, seen INTEGER DEFAULT 0)""")
    return db

def create(title: str, url: str, kind: str = "change", target: str = ""):
    db = _db()
    cur = db.execute("INSERT INTO goals(title, url, kind, target, last_value, active, created, last_check) VALUES(?,?,?,?,?,?,?,?)",
                     (title, url, kind, target, "", 1, time.time(), 0))
    db.commit()
    return {"ok": True, "id": cur.lastrowid}

def list_all():
    db = _db()
    return [{"id": r[0], "title": r[1], "url": r[2], "kind": r[3], "target": r[4],
             "last_value": r[5], "active": bool(r[6])}
            for r in db.execute("SELECT id, title, url, kind, target, last_value, active FROM goals ORDER BY id DESC")]

def remove(gid: int):
    db = _db()
    db.execute("DELETE FROM goals WHERE id=?", (gid,))
    db.commit()
    return {"ok": True}

def alerts(unseen_only: bool = False):
    db = _db()
    q = "SELECT id, gid, text, ts FROM goal_alerts"
    if unseen_only:
        q += " WHERE seen=0"
    q += " ORDER BY ts DESC LIMIT 20"
    rows = db.execute(q).fetchall()
    return [{"id": r[0], "gid": r[1], "text": r[2], "ts": r[3]} for r in rows]

def mark_seen(aid: int):
    db = _db()
    db.execute("UPDATE goal_alerts SET seen=1 WHERE id=?", (aid,))
    db.commit()
    return {"ok": True}

def _fetch_text(url: str) -> str:
    import httpx
    if not url.startswith("http"):
        url = "https://" + url
    r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25, follow_redirects=True)
    txt = re.sub(r"<script.*?</script>|<style.*?</style>", " ", r.text, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", txt))

def _prices(txt: str):
    return re.findall(r"₹\s?[\d,]+(?:\.\d+)?|\$\s?[\d,]+(?:\.\d+)?", txt)

def check_once(gid: int = 0):
    """Check one/all goals. Returns new alerts. Dedup: same value twice never re-alerts."""
    db = _db()
    rows = db.execute("SELECT id, title, url, kind, target, last_value FROM goals WHERE active=1" +
                      (" AND id=?" if gid else ""), ((gid,) if gid else ())).fetchall()
    new = []
    for _id, title, url, kind, target, last in rows:
        try:
            txt = _fetch_text(url)
        except Exception as e:
            continue
        val, fire, msg = "", False, ""
        if kind == "price":
            ps = _prices(txt)
            val = ps[0] if ps else ""
            if val and last and val != last:
                fire, msg = True, f"{title}: price {last} → {val}"
        elif kind == "text":
            hit = target.lower() in txt.lower() if target else False
            val = "present" if hit else "absent"
            if last and val != last:
                fire, msg = True, f"{title}: '{target}' is now {val}"
        else:  # change
            val = hashlib.sha256(txt.encode()).hexdigest()[:16]
            if last and val != last:
                fire, msg = True, f"{title}: page changed"
        db.execute("UPDATE goals SET last_value=?, last_check=? WHERE id=?", (val, time.time(), _id))
        if fire:
            db.execute("INSERT INTO goal_alerts(gid, text, ts) VALUES(?,?,?)", (_id, msg, time.time()))
            new.append({"gid": _id, "text": msg})
    db.commit()
    return new

_started = False

def start_loop(push=None, interval: int = 300):
    """Background thread. push(alerts) called (awaitable) so WS/bell update."""
    global _started
    if _started:
        return
    _started = True

    def _loop():
        import asyncio
        while True:
            try:
                new = check_once()
                if new and push:
                    try:
                        asyncio.run(push())
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(interval)
    threading.Thread(target=_loop, daemon=True).start()
