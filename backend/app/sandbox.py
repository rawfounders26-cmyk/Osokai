"""Marketplace sandbox — signed is not enough; enforced is what counts.

- `KNOWN_PERMS` with risk tiers; high-risk packs need explicit `ack` at install.
- `grants` ledger: what each installed pack may do. `check()` + `guard()`
  are the runtime gates any executor calls before acting for a pack.
- Publisher reputation from installs + star ratings; low-rep packs install
  with a warning, not a block (user stays in charge).
"""
import os
import sqlite3
import time

try:
    from app.paths import data as _pdata
except ImportError:
    from paths import data as _pdata

DB = _pdata("osokai.db")

KNOWN_PERMS = {
    "loops.write": "medium", "files.read": "low", "files.write": "high",
    "browser.control": "high", "vault.read": "critical", "net.fetch": "medium",
    "calendar.write": "medium", "email.send": "high",
}
HIGH_RISK = {p for p, r in KNOWN_PERMS.items() if r in ("high", "critical")}
MIN_REP_WARN = 2.5


def _db():
    db = sqlite3.connect(os.path.normpath(DB), check_same_thread=False)
    db.execute("CREATE TABLE IF NOT EXISTS perm_grants(skill TEXT, perm TEXT, ts REAL, PRIMARY KEY(skill, perm))")
    db.execute("""CREATE TABLE IF NOT EXISTS perm_audit(
        id INTEGER PRIMARY KEY, skill TEXT, perm TEXT, allowed INT, ts REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS pack_ratings(
        skill TEXT, user TEXT, stars INT, ts REAL, PRIMARY KEY(skill, user))""")
    return db


def grants_for(skill: str):
    return [r[0] for r in _db().execute("SELECT perm FROM perm_grants WHERE skill=?", (skill,)).fetchall()]


def check(skill: str, perm: str) -> bool:
    """Runtime gate. Unknown perms default-deny. Every check is audited."""
    allowed = perm in KNOWN_PERMS and _db().execute(
        "SELECT 1 FROM perm_grants WHERE skill=? AND perm=?", (skill, perm)).fetchone() is not None
    try:
        db = _db()
        db.execute("INSERT INTO perm_audit(skill, perm, allowed, ts) VALUES(?,?,?,?)",
                   (skill, perm, 1 if allowed else 0, time.time()))
        db.commit()
    except Exception:
        pass
    return allowed


def guard(skill: str, perm: str):
    if not check(skill, perm):
        raise PermissionError(f"pack '{skill}' lacks permission '{perm}'")
    return True


def grant(skill: str, perms) -> dict:
    db = _db()
    for p in perms or []:
        if p in KNOWN_PERMS:
            db.execute("INSERT OR REPLACE INTO perm_grants(skill, perm, ts) VALUES(?,?,?)", (skill, p, time.time()))
    db.commit()
    return {"ok": True, "grants": grants_for(skill)}


def revoke(skill: str) -> dict:
    db = _db()
    db.execute("DELETE FROM perm_grants WHERE skill=?", (skill,))
    db.commit()
    return {"ok": True}


def rate(skill: str, user: str, stars: int) -> dict:
    db = _db()
    db.execute("INSERT OR REPLACE INTO pack_ratings(skill, user, stars, ts) VALUES(?,?,?,?)",
               (skill, user[:120], max(1, min(5, stars)), time.time()))
    db.commit()
    return reputation(skill)


def reputation(skill: str) -> dict:
    db = _db()
    installs = 0
    try:
        r = db.execute("SELECT COUNT(*) FROM market_installed WHERE name=?", (skill,)).fetchone()
        installs = r[0] if r else 0
    except Exception:
        pass
    rows = db.execute("SELECT stars FROM pack_ratings WHERE skill=?", (skill,)).fetchall()
    avg = round(sum(r[0] for r in rows) / len(rows), 2) if rows else 0.0
    return {"skill": skill, "installs": installs, "ratings": len(rows), "stars": avg,
            "warn": bool(avg and avg < MIN_REP_WARN)}
