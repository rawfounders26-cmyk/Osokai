"""Profile — who the user is (identity), separate from secrets (vault).
Name/city/budget live here in plaintext. Passwords/CVV/tokens NEVER do."""
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

PROFILE_KEYS = ("name", "city", "upi_id", "budget_default", "currency")

def _db():
    db = _hardb(os.path.normpath(DB))
    db.execute("CREATE TABLE IF NOT EXISTS profile(key TEXT PRIMARY KEY, value TEXT, updated REAL)")
    db.execute("""CREATE TABLE IF NOT EXISTS prefs(
        id INTEGER PRIMARY KEY, domain TEXT, pref TEXT, ts REAL)""")
    return db

def get_profile():
    db = _db()
    rows = {r[0]: r[1] for r in db.execute("SELECT key, value FROM profile")}
    return {k: rows.get(k, "") for k in PROFILE_KEYS}

def set_profile(key: str, value: str):
    if key not in PROFILE_KEYS:
        return {"ok": False, "error": f"unknown key (allowed: {', '.join(PROFILE_KEYS)})"}
    db = _db()
    db.execute("INSERT OR REPLACE INTO profile(key, value, updated) VALUES(?,?,?)",
               (key, value, time.time()))
    db.commit()
    return {"ok": True, "key": key}

def add_pref(domain: str, pref: str):
    db = _db()
    db.execute("INSERT INTO prefs(domain, pref, ts) VALUES(?,?,?)", (domain, pref, time.time()))
    db.commit()
    return {"ok": True}

def get_prefs(domain: str = ""):
    db = _db()
    q = "SELECT pref FROM prefs"
    args = []
    if domain:
        q += " WHERE domain=?"
        args.append(domain)
    q += " ORDER BY ts DESC LIMIT 20"
    return [r[0] for r in db.execute(q, args)]

def context_block():
    """Injected into agent runs: identity + budgets + prefs. Secrets never included."""
    p = get_profile()
    lines = []
    if p.get("name"):
        lines.append(f"user: {p['name']}")
    if p.get("city"):
        lines.append(f"city: {p['city']}")
    if p.get("budget_default"):
        lines.append(f"default budget: {p['budget_default']}")
    for d in ("shopping", "style", "general"):
        for pref in get_prefs(d):
            lines.append(f"pref [{d}]: {pref}")
    return "\n".join(lines)
