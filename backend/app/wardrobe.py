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
    for col in ("likes INTEGER DEFAULT 0", "dislikes INTEGER DEFAULT 0"):
        try:
            db.execute(f"ALTER TABLE wardrobe ADD COLUMN {col}")
        except Exception:
            pass
    db.execute("CREATE TABLE IF NOT EXISTS style_prefs(id INTEGER PRIMARY KEY, pref TEXT, ts REAL)")
    db.execute("CREATE TABLE IF NOT EXISTS wardrobe_cfg(key TEXT PRIMARY KEY, val TEXT)")
    return db


def get_cfg(key: str, default: str = "") -> str:
    try:
        r = _db().execute("SELECT val FROM wardrobe_cfg WHERE key=?", (key,)).fetchone()
        return r[0] if r else default
    except Exception:
        return default


def set_cfg(key: str, val: str) -> dict:
    db = _db()
    db.execute("INSERT OR REPLACE INTO wardrobe_cfg(key, val) VALUES(?,?)", (key, val))
    db.commit()
    return {"ok": True}


def laundry_days() -> int:
    try:
        return max(1, int(get_cfg("laundry_days", "7")))
    except Exception:
        return 7


def laundry_done() -> dict:
    """Fresh cycle: everything wearable again."""
    db = _db()
    db.execute("UPDATE wardrobe SET last_worn=0")
    db.commit()
    return {"ok": True}


# occasion keyword -> formality. Calendar-aware planning rides on this.
OCCASIONS = {
    "wedding": "formal", "reception": "formal", "funeral": "formal",
    "interview": "formal", "conference": "formal", "gala": "formal",
    "meeting": "smart-casual", "office": "smart-casual", "work": "smart-casual",
    "presentation": "smart-casual", "demo": "smart-casual", "date": "smart-casual",
    "party": "smart-casual", "dinner": "smart-casual", "event": "smart-casual",
    "gym": "activewear", "workout": "activewear", "run": "activewear",
    "yoga": "activewear", "trek": "activewear", "cricket": "activewear",
    "beach": "casual", "vacation": "casual", "trip": "casual", "travel": "casual",
    "temple": "smart-casual", "church": "smart-casual", "festival": "smart-casual",
}


def occasion_formality(text: str) -> str:
    t = (text or "").lower()
    for kw, f in OCCASIONS.items():
        if kw in t:
            return f
    return ""


def score(item: dict) -> float:
    """Learning loop: likes and wears up, dislikes down hard, stale items decay in."""
    s = item.get("likes", 0) * 3 + item.get("wears", 0) - item.get("dislikes", 0) * 4
    if not item.get("last_worn"):
        s += 1  # unworn-new gets a fair trial, then earns its rank
    return s

def add_item(category: str, color: str = "", season: str = "all",
             formality: str = "casual"):
    db = _db()
    cur = db.execute("INSERT INTO wardrobe(category, color, season, formality) VALUES(?,?,?,?)",
                     (category, color, season, formality))
    db.commit()
    return {"ok": True, "id": cur.lastrowid}

def list_items(season: str = "", formality: str = ""):
    db = _db()
    q = "SELECT id, category, color, season, formality, last_worn, wears, likes, dislikes FROM wardrobe"
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
             "formality": r[4], "last_worn": r[5], "wears": r[6],
             "likes": r[7] or 0, "dislikes": r[8] or 0} for r in rows]

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
        db.execute("UPDATE wardrobe SET wears=wears+1, likes=likes+1 WHERE id=?", (item_id,))
    else:
        db.execute("UPDATE wardrobe SET dislikes=dislikes+1 WHERE id=?", (item_id,))
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

def suggest(season_hint: str = "", formality: str = "", days_rewear: int = 0):
    """Code picks candidates (season + laundry guard + learned scores); LLM words the pick."""
    items = list_items()
    now = time.time()
    guard = (days_rewear or laundry_days()) * 86400
    fresh = [i for i in items if not i["last_worn"] or (now - i["last_worn"]) > guard]
    pool = fresh or items  # laundry week from hell: everything's worn, still dress the human
    if formality:
        f = [i for i in pool if i["formality"] == formality]
        pool = f or pool
    pool = sorted(pool, key=score, reverse=True)
    for i in pool:
        i["score"] = round(score(i), 1)
    return {"candidates": pool[:12], "prefs": get_prefs(), "weather": weather(),
            "count": len(items), "laundry_days": laundry_days()}


def _fmt(items) -> str:
    return ", ".join(f"{i.get('color','')} {i['category']}".strip() for i in items)


def plan_occasion(occasion: str, day: str = "") -> dict:
    """Calendar-aware look: finds the event, reads its formality, scores the picks."""
    try:
        try:
            from app import calendar as _cal
        except ImportError:
            import calendar as _cal
        evs = _cal.list_all(day) if day else []
    except Exception:
        evs = []
    match = next((e for e in evs if occasion.lower() in (e.get("title") or "").lower()), None)
    event = (match or {}).get("title", "") if evs else ""
    formality = occasion_formality(occasion) or occasion_formality(event) or "smart-casual"
    s = suggest(formality=formality)
    picks = s["candidates"][:3]
    w = s["weather"]
    wx = f"{w.get('temp')}°C" if w.get("temp") is not None else "weather n/a"
    line = f"{occasion.title()}" + (f" ({event}, {day})" if event else "") + f" — {wx}: {_fmt(picks)}."
    if not picks:
        line = f"Wardrobe is empty — add a few items first, then ask again for {occasion}."
    return {"ok": True, "occasion": occasion, "event": event, "formality": formality,
            "picks": picks, "weather": w, "reply": line}


def plan_week() -> dict:
    """7-day plan: each day's formality from its calendar events, no repeats."""
    try:
        try:
            from app import calendar as _cal
        except ImportError:
            import calendar as _cal
    except Exception:
        _cal = None
    import datetime as _dt
    used, days = set(), []
    for off in range(7):
        d = _dt.date.today() + _dt.timedelta(days=off)
        iso = d.isoformat()
        evs = []
        try:
            evs = _cal.list_all(iso) if _cal else []
        except Exception:
            pass
        f = ""
        for e in evs:
            f = occasion_formality(e.get("title", "")) or f
        if not f:
            f = "casual" if d.weekday() >= 5 else "smart-casual"
        cands = [i for i in suggest(formality=f)["candidates"] if i["id"] not in used] or \
                [i for i in suggest()["candidates"] if i["id"] not in used]
        picks = cands[:2]
        used.update(i["id"] for i in picks)
        label = d.strftime("%a %d %b")
        ev = evs[0]["title"] if evs else ("weekend" if d.weekday() >= 5 else "office day")
        days.append({"day": label, "event": ev, "formality": f,
                     "wear": _fmt(picks) or "— wardrobe running low, laundry soon?"})
    return {"ok": True, "days": days,
            "reply": "Your week:\n" + "\n".join(f"• {d['day']} ({d['event']}): {d['wear']}" for d in days)}


def pack_trip(days: int, dest: str = "") -> dict:
    """Packing list scaled to trip length + weather: tops, bottoms, layers, one sharp set."""
    days = max(1, min(30, days))
    items = list_items()
    if not items:
        return {"ok": False, "reply": "Wardrobe is empty — add items before packing."}
    w = weather()
    hot = (w.get("temp") or 30) >= 28
    need_tops = days + 1
    need_bottoms = max(2, (days + 1) // 2)
    ranked = sorted(items, key=score, reverse=True)
    tops = [i for i in ranked if any(k in i["category"] for k in ("shirt", "tshirt", "tee", "top", "kurta"))][:need_tops]
    bottoms = [i for i in ranked if any(k in i["category"] for k in ("jean", "pant", "trouser", "short", "skirt"))][:need_bottoms]
    formal = [i for i in ranked if i["formality"] == "formal"][:2]
    active = [i for i in ranked if i["formality"] == "activewear"][:1]
    lines = [f"Pack for {days} day(s)" + (f" in {dest}" if dest else "") + f" ({w.get('temp')}°C):",
             f"• Tops x{len(tops)}: {_fmt(tops)}",
             f"• Bottoms x{len(bottoms)}: {_fmt(bottoms)}"]
    if formal:
        lines.append(f"• One sharp set: {_fmt(formal)}")
    if active:
        lines.append(f"• Active: {_fmt(active)}")
    if not hot:
        lines.append("• Layer up — nights look cool. Add a jacket.")
    if (w.get("precip") or 0) > 0:
        lines.append("• Rain on the radar — pack something water-resistant.")
    return {"ok": True, "days": days, "dest": dest, "weather": w,
            "tops": tops, "bottoms": bottoms, "formal": formal,
            "reply": "\n".join(lines)}


def intake_image(b64_image: str) -> dict:
    """Photo -> vision describes the garment -> wardrobe item. Fail-soft."""
    try:
        try:
            from app.grok_client import chat_with_vision
        except ImportError:
            from grok_client import chat_with_vision
    except Exception as e:
        return {"ok": False, "reply": f"vision unavailable: {e}"}
    raw = chat_with_vision(
        "Describe this clothing item in JSON ONLY: "
        '{"category": "...", "color": "...", "season": "all|summer|winter|monsoon", '
        '"formality": "casual|smart-casual|formal|activewear"}. No other text.', b64_image)
    if raw.startswith("[osok"):
        return {"ok": False, "reply": raw}
    import json as _j, re as _re
    try:
        s, e = raw.find("{"), raw.rfind("}")
        d = _j.loads(raw[s:e + 1])
        r = add_item(d.get("category", "item"), d.get("color", ""),
                     d.get("season", "all") if d.get("season") in ("all", "summer", "winter", "monsoon") else "all",
                     d.get("formality", "casual") if d.get("formality") in ("casual", "smart-casual", "formal", "activewear") else "casual")
        return {"ok": True, "id": r["id"],
                "reply": f"Added: {d.get('color','')} {d.get('category','')} ({d.get('formality','casual')})."}
    except Exception:
        return {"ok": False, "reply": "Couldn't read that photo — try better light, one item at a time."}
