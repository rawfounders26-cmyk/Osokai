"""Wardrobe — outfit planner store. Items + style memory, SQLite next to memory turns."""
import sqlite3, os, time

try:
    from app.paths import data as _pdata
except ImportError:
    from paths import data as _pdata

DB = _pdata("osokai.db")

def _db():
    db = sqlite3.connect(os.path.normpath(DB), check_same_thread=False)
    db.execute("""CREATE TABLE IF NOT EXISTS wardrobe(
        id INTEGER PRIMARY KEY, category TEXT, color TEXT, season TEXT,
        formality TEXT, last_worn REAL DEFAULT 0, wears INTEGER DEFAULT 0)""")
    db.execute("CREATE TABLE IF NOT EXISTS style_prefs(id INTEGER PRIMARY KEY, pref TEXT, ts REAL)")
    return db

def add_item(category: str, color: str = "", season: str = "all",
             formality: str = "casual"):
    db = _db()
    cur = db.execute("INSERT INTO wardrobe(category, color, season, formality) VALUES(?,?,?,?)",
                     (category, color, season, formality))
    db.commit()
    return {"ok": True, "id": cur.lastrowid}

def list_items(season: str = "", formality: str = ""):
    db = _db()
    q = "SELECT id, category, color, season, formality, last_worn, wears FROM wardrobe"
    conds, args = [], []
    if season:
        conds.append("(season='all' OR season=?)")
        args.append(season)
    if formality:
        conds.append("formality=?")
        args.append(formality)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    rows = db.execute(q, args).fetchall()
    return [{"id": r[0], "category": r[1], "color": r[2], "season": r[3],
             "formality": r[4], "last_worn": r[5], "wears": r[6]} for r in rows]

def mark_worn(item_id: int):
    db = _db()
    db.execute("UPDATE wardrobe SET last_worn=?, wears=wears+1 WHERE id=?", (time.time(), item_id))
    db.commit()
    return {"ok": True}

def add_pref(pref: str):
    db = _db()
    db.execute("INSERT INTO style_prefs(pref, ts) VALUES(?,?)", (pref, time.time()))
    db.commit()
    return {"ok": True}

def get_prefs():
    db = _db()
    return [r[0] for r in db.execute("SELECT pref FROM style_prefs ORDER BY ts DESC LIMIT 20")]

def feedback(item_id: int, good: bool, note: str = ""):
    db = _db()
    if good:
        db.execute("UPDATE wardrobe SET wears=wears+1 WHERE id=?", (item_id,))
    else:
        r = db.execute("SELECT category, color, season FROM wardrobe WHERE id=?", (item_id,)).fetchone()
        if r:
            db.execute("INSERT INTO style_prefs(pref, ts) VALUES(?,?)",
                       (f"disliked {r[1]} {r[0]} ({r[2]})" + (f" — {note}" if note else ""), time.time()))
    if note and good:
        db.execute("INSERT INTO style_prefs(pref, ts) VALUES(?,?)", (note, time.time()))
    db.commit()
    return {"ok": True}

def weather(lat: float = 13.08, lon: float = 80.27):
    """Open-Meteo, free, no key. Defaults: Chennai."""
    import httpx
    try:
        r = httpx.get("https://api.open-meteo.com/v1/forecast",
                      params={"latitude": lat, "longitude": lon, "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code"},
                      timeout=15)
        c = r.json().get("current", {})
        return {"temp": c.get("temperature_2m"), "humidity": c.get("relative_humidity_2m"),
                "precip": c.get("precipitation"), "code": c.get("weather_code")}
    except Exception as e:
        return {"error": str(e)[:150]}

def suggest(season_hint: str = "", formality: str = "", days_rewear: int = 2):
    """Code picks candidates (season + rewear guard); LLM words the pick. Returns data."""
    items = list_items()
    now = time.time()
    fresh = [i for i in items
             if not i["last_worn"] or (now - i["last_worn"]) > days_rewear * 86400]
    pool = fresh or items
    if formality:
        f = [i for i in pool if i["formality"] == formality]
        pool = f or pool
    return {"candidates": pool[:12], "prefs": get_prefs(), "weather": weather(),
            "count": len(items)}
