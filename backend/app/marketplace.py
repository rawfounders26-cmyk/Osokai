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

try:
    from app.db import connect as _hardb
except ImportError:
    from db import connect as _hardb
BASE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "skills"))
ROLES = os.path.join(BASE, "roles")
MARKET = os.path.join(BASE, "market")
DB = _pdata("osokai.db")


def _db():
    db = _hardb(os.path.normpath(DB))
    db.execute("""CREATE TABLE IF NOT EXISTS market_installed(
        name TEXT PRIMARY KEY, version TEXT, ts REAL, enabled INTEGER DEFAULT 1)""")
    return db


def _key() -> bytes:
    return os.getenv("OSOKAI_AUTH_TOKEN", "osokai-dev").encode()


def _invalidate_router_cache():
    try:
        try:
            import app.skills_index as _si
        except ImportError:
            import skills_index as _si
        _si._cache = None  # rescan roles dir on next route()
    except Exception:
        pass


def _canonical_manifest(man: dict) -> str:
    sub = {k: man.get(k, "") for k in ("name", "version", "description", "perms")}
    return json.dumps(sub, sort_keys=True, separators=(",", ":"))


def sign_pack(skill_md: bytes, manifest: dict = None) -> str:
    """v2 signature: HMAC over content hash + canonical metadata. Body-only
    legacy packs still verify (fallback) but new packs must use v2."""
    if manifest is None:
        return hmac.new(_key(), skill_md, hashlib.sha256).hexdigest()
    inner = hashlib.sha256(skill_md).hexdigest() + "\n" + _canonical_manifest(manifest)
    return hmac.new(_key(), inner.encode(), hashlib.sha256).hexdigest()


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
    man_nosig = {k: v for k, v in man.items() if k != "sig"}
    if hmac.compare_digest(sign_pack(body, man_nosig), man.get("sig", "")):
        return {"ok": True, "manifest": man, "scheme": "v2"}
    if hmac.compare_digest(sign_pack(body), man.get("sig", "")):
        return {"ok": True, "manifest": man, "scheme": "v1-legacy",
                "warning": "pack uses legacy body-only signature — republish to v2"}
    return {"ok": False, "error": "bad signature — untrusted publisher"}


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


def install(name: str, ack_high_risk: bool = False) -> dict:
    v = verify(name)
    if not v["ok"]:
        return v
    try:
        from app.sandbox import HIGH_RISK, grant, reputation, MIN_REP_WARN
    except ImportError:
        from sandbox import HIGH_RISK, grant, reputation, MIN_REP_WARN
    risky = [p for p in v["manifest"].get("perms", []) if p in HIGH_RISK]
    if risky and not ack_high_risk:
        return {"ok": False, "error": f"high-risk permissions need explicit ack: {risky}",
                "ack_required": risky}
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
    grant(name, v["manifest"].get("perms", []))  # sandbox ledger: declared perms only
    rep = reputation(name)
    _invalidate_router_cache()
    out = {"ok": True, "installed": name}
    if rep.get("warn"):
        out["warning"] = f"low publisher rating ({rep['stars']}★) — review the pack before enabling"
    return out


def set_enabled(name: str, enabled: bool) -> dict:
    db = _db()
    if not db.execute("SELECT 1 FROM market_installed WHERE name=?", (name,)).fetchone():
        return {"ok": False, "error": "not an installed pack"}
    db.execute("UPDATE market_installed SET enabled=? WHERE name=?", (1 if enabled else 0, name))
    db.commit()
    _invalidate_router_cache()
    return {"ok": True, "name": name, "enabled": enabled}


def uninstall(name: str) -> dict:
    """Removal only touches exact installed-pack dirs — never built-ins, never roots."""
    if not name or name.strip() in ("", ".", "..") or "/" in name or "\\" in name:
        return {"ok": False, "error": "bad pack name"}
    db = _db()
    row = db.execute("SELECT name FROM market_installed WHERE name=?", (name,)).fetchone()
    if not row:
        return {"ok": False, "error": "not an installed market pack — built-ins are protected"}
    dest = os.path.normpath(os.path.join(ROLES, name))
    if dest == os.path.normpath(ROLES) or not dest.startswith(os.path.normpath(ROLES) + os.sep):
        return {"ok": False, "error": "refusing: resolves outside pack dir"}
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    db.execute("DELETE FROM market_installed WHERE name=?", (name,))
    db.commit()
    try:
        try:
            from app.sandbox import revoke
        except ImportError:
            from sandbox import revoke
        revoke(name)
    except Exception:
        pass
    _invalidate_router_cache()
    return {"ok": True, "removed": name}
