"""Skill marketplace — community skills, signed and sandbox-gated.

Every pack ships manifest.json {name, version, description, perms[], sha256, sig}.
`sig` = HMAC-SHA256 of the SKILL.md bytes keyed by the server auth token, so
only packs published from a trusted Osok-AI instance install cleanly.
Install = verified copy into skills/roles + registry record. Removal never
touches built-in roles.
"""
import hashlib
import hmac
import json
import os
import shutil
import sqlite3
import time

try:
    from app.paths import data as _pdata
except ImportError:
    from paths import data as _pdata

BASE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "skills"))
ROLES = os.path.join(BASE, "roles")
MARKET = os.path.join(BASE, "market")
DB = _pdata("osokai.db")


def _db():
    db = sqlite3.connect(os.path.normpath(DB), check_same_thread=False)
    db.execute("""CREATE TABLE IF NOT EXISTS market_installed(
        name TEXT PRIMARY KEY, version TEXT, ts REAL, enabled INTEGER DEFAULT 1)""")
    return db


def _key() -> bytes:
    return os.getenv("OSOKAI_AUTH_TOKEN", "osokai-dev").encode()


def sign_pack(skill_md: bytes) -> str:
    return hmac.new(_key(), skill_md, hashlib.sha256).hexdigest()


def _read_pack(name: str):
    d = os.path.normpath(os.path.join(MARKET, name))
    if not d.startswith(MARKET) or not os.path.isdir(d):
        return None, "not found"
    try:
        man = json.load(open(os.path.join(d, "manifest.json"), encoding="utf-8"))
        body = open(os.path.join(d, "SKILL.md"), encoding="utf-8").read()
    except Exception as e:
        return None, f"bad pack: {e}"
    return {"manifest": man, "body": body, "dir": d}, ""


def verify(name: str) -> dict:
    pack, err = _read_pack(name)
    if not pack:
        return {"ok": False, "error": err}
    man = pack["manifest"]
    body = pack["body"].encode()
    if hashlib.sha256(body).hexdigest() != man.get("sha256", ""):
        return {"ok": False, "error": "checksum mismatch — pack tampered"}
    if not hmac.compare_digest(sign_pack(body), man.get("sig", "")):
        return {"ok": False, "error": "bad signature — untrusted publisher"}
    return {"ok": True, "manifest": man}


def list_market():
    out = []
    if not os.path.isdir(MARKET):
        return out
    installed = {r[0]: (r[1], bool(r[2])) for r in
                 _db().execute("SELECT name, version, enabled FROM market_installed").fetchall()}
    for name in sorted(os.listdir(MARKET)):
        pack, _ = _read_pack(name)
        if not pack:
            continue
        man = pack["manifest"]
        ver, en = installed.get(name, ("", True))
        out.append({"name": name, "version": man.get("version", "?"),
                    "description": man.get("description", ""),
                    "perms": man.get("perms", []),
                    "installed": name in installed, "installed_version": ver, "enabled": en,
                    "verified": verify(name)["ok"]})
    return out


def install(name: str) -> dict:
    v = verify(name)
    if not v["ok"]:
        return v
    pack, _ = _read_pack(name)
    dest = os.path.normpath(os.path.join(ROLES, name))
    if not dest.startswith(ROLES):
        return {"ok": False, "error": "bad name"}
    os.makedirs(ROLES, exist_ok=True)
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    shutil.copytree(pack["dir"], dest)
    for f in os.listdir(dest):
        if f != "SKILL.md":
            try:
                os.remove(os.path.join(dest, f))
            except Exception:
                pass
    db = _db()
    db.execute("INSERT OR REPLACE INTO market_installed(name, version, ts, enabled) VALUES(?,?,?,?)",
               (name, v["manifest"].get("version", "?"), time.time(), 1))
    db.commit()
    try:
        try:
            import app.skills_index as _si
        except ImportError:
            import skills_index as _si
        _si._cache = None  # rescan roles dir on next route()
    except Exception:
        pass
    return {"ok": True, "installed": name}


def set_enabled(name: str, enabled: bool) -> dict:
    db = _db()
    db.execute("UPDATE market_installed SET enabled=? WHERE name=?", (1 if enabled else 0, name))
    db.commit()
    return {"ok": True, "name": name, "enabled": enabled}


def uninstall(name: str) -> dict:
    dest = os.path.normpath(os.path.join(ROLES, name))
    if dest.startswith(ROLES) and os.path.isdir(dest):
        shutil.rmtree(dest)
    db = _db()
    db.execute("DELETE FROM market_installed WHERE name=?", (name,))
    db.commit()
    return {"ok": True, "removed": name}
