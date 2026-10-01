"""Encrypted vault — cards (incl. CVV), logins, service tokens.
AES-128 Fernet. Key lives ONLY in backend/.env (OSOKAI_VAULT_KEY), never leaves the PC.
Values are decrypted in memory solely to fill platform fields after user approval."""
import base64
import os
import re
from cryptography.fernet import Fernet, InvalidToken

try:
    from app.paths import data as _pdata
except ImportError:
    from paths import data as _pdata

def _key() -> bytes:
    raw = os.getenv("OSOKAI_VAULT_KEY", "")
    if not raw:
        raise RuntimeError("OSOKAI_VAULT_KEY missing in backend/.env")
    try:
        return base64.urlsafe_b64decode(raw.encode())
    except Exception:
        raise RuntimeError("OSOKAI_VAULT_KEY is not valid base64")

def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(_key()))

def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()

def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        raise RuntimeError("vault key mismatch — cannot decrypt")

def mask(value: str, keep: int = 4) -> str:
    v = value or ""
    if len(v) <= keep:
        return "•" * len(v)
    return "•" * (len(v) - keep) + v[-keep:]


# ---- generic secret store (cards incl. CVV, logins). Ciphertext only on disk. ----
import json as _json
import time as _time

try:
    from app.paths import data as _pdata, atomic_write_json as _atomic_json
except ImportError:
    from paths import data as _pdata, atomic_write_json as _atomic_json

# F09: vault store lives in the persistent data dir (survives container replacement)
_STORE = _pdata("vault_secrets.json")
_scache = {"mtime": 0, "data": {}}

def _migrate_store():
    """One-time move from the legacy source-tree path. Never deletes the original."""
    legacy = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "vault_secrets.json"))
    try:
        if not os.path.isfile(os.path.normpath(_STORE)) and os.path.isfile(legacy):
            import shutil as _sh
            _sh.copy2(legacy, os.path.normpath(_STORE))
    except Exception:
        pass

_migrate_store()

def _read_store():
    try:
        fp = os.path.normpath(_STORE)
        mt = os.path.getmtime(fp)
        if mt == _scache["mtime"]:
            return _scache["data"]
        data = _json.load(open(fp))
        _scache.update(mtime=mt, data=data)
        return data
    except Exception:
        return {}

def _write_store(d):
    _atomic_json(os.path.normpath(_STORE), d)
    _scache.update(mtime=0, data=d)

def secret_set(scope: str, key: str, value: str, policy: str = "while-unlocked", domains=None):
    if not key or not value:
        raise ValueError("key and value required")
    if policy not in ("always", "while-unlocked", "never"):
        policy = "while-unlocked"
    d = _read_store()
    prev = d.get(key, {})
    d[key] = {"scope": scope or "general", "enc": encrypt(value),
              "len": len(value), "updated": _time.strftime("%Y-%m-%dT%H:%M:%S"),
              "policy": prev.get("policy", policy),
              "domains": prev.get("domains", domains or [])}
    _write_store(d)
    return {"ok": True, "key": key, "scope": d[key]["scope"], "masked": mask(value)}

def secret_list():
    d = _read_store()
    out = []
    for k, v in d.items():
        try:
            masked = mask(decrypt(v["enc"]))
        except Exception:
            masked = "•unreadable•"
        out.append({"key": k, "scope": v.get("scope", "general"), "masked": masked,
                    "updated": v.get("updated", ""), "policy": v.get("policy", "while-unlocked"),
                    "domains": v.get("domains", [])})
    return out

def secret_policy(key: str, policy: str = "", domains=None):
    d = _read_store()
    if key not in d:
        raise KeyError(f"no secret: {key}")
    if policy:
        if policy not in ("always", "while-unlocked", "never"):
            raise ValueError("policy must be always|while-unlocked|never")
        d[key]["policy"] = policy
    if domains is not None:
        d[key]["domains"] = [str(x).lower() for x in domains]
    _write_store(d)
    e = d[key]
    return {"ok": True, "key": key, "policy": e["policy"], "domains": e["domains"]}

def _norm_host(domain: str) -> str:
    """Lowercase hostname without scheme/port/path. Empty string stays empty (= denied)."""
    d = (domain or "").strip().lower()
    d = re.sub(r"^[a-z][a-z0-9+.-]*://", "", d)
    d = d.split("/")[0].split("?")[0].split("#")[0]
    if "@" in d:
        d = d.rsplit("@", 1)[1]
    d = d.split(":")[0].strip().strip(".")
    return d


def _domain_allowed(host: str, allowed: list) -> bool:
    if not host or not allowed:
        return False  # empty domain never bypasses; unrestricted handled by caller
    return any(host == a or host.endswith("." + a) for a in allowed)

def secret_fill(key: str, domain: str = "", device: str = "?") -> str:
    """Decrypt for field entry — the single enforcement gate.
    Checks policy -> lock -> domain, then writes the audit row."""
    d = _read_store()
    if key not in d:
        _audit(key, domain, device, False, "missing")
        raise KeyError(f"no secret: {key}")
    e = d[key]
    pol = e.get("policy", "while-unlocked")
    if pol == "never":
        _audit(key, domain, device, False, "policy=never")
        raise PermissionError("policy=never for " + key)
    if pol == "while-unlocked" and not is_unlocked():
        _audit(key, domain, device, False, "locked")
        raise PermissionError("vault locked — unlock first")
    allowed = [x.lower().strip().strip(".") for x in (e.get("domains") or []) if str(x).strip()]
    if allowed and not _domain_allowed(_norm_host(domain), allowed):
        _audit(key, domain, device, False, "domain denied")
        raise PermissionError(f"{key} not allowed on {domain}")
    val = decrypt(e["enc"])
    _audit(key, domain, device, True, "ok")
    return val

def secret_delete(key: str):
    d = _read_store()
    d.pop(key, None)
    _write_store(d)
    return {"ok": True, "key": key}


# ---- lock state: locked by default, unlocks for a window (Hello-gated next) ----
_lock = {"until": 0}

def is_unlocked() -> bool:
    return _lock["until"] > _time.time()

def lock():
    _lock["until"] = 0
    return {"ok": True, "locked": True}

def unlock(minutes: int = 15):
    _lock["until"] = _time.time() + max(1, minutes) * 60
    return {"ok": True, "locked": False, "for_minutes": minutes}

def lock_status():
    left = max(0, int(_lock["until"] - _time.time()))
    return {"locked": left <= 0, "seconds_left": left}


# ---- audit log: every AI/human access attempt, allow + deny ----
import sqlite3 as _sql

_DB = _pdata("osokai.db")

def _adb():
    db = _sql.connect(os.path.normpath(_DB), check_same_thread=False)
    db.execute("""CREATE TABLE IF NOT EXISTS vault_access(
        id INTEGER PRIMARY KEY, key TEXT, domain TEXT, device TEXT,
        allowed INTEGER, reason TEXT, ts REAL)""")
    return db

def _audit(key: str, domain: str, device: str, allowed: bool, reason: str):
    try:
        db = _adb()
        db.execute("INSERT INTO vault_access(key, domain, device, allowed, reason, ts) VALUES(?,?,?,?,?,?)",
                   (key, domain or "", device or "?", 1 if allowed else 0, reason, _time.time()))
        db.commit()
    except Exception:
        pass

def audit_list(limit: int = 50):
    db = _adb()
    rows = db.execute("SELECT key, domain, device, allowed, reason, ts FROM vault_access ORDER BY id DESC LIMIT ?",
                      (limit,)).fetchall()
    return [{"key": r[0], "domain": r[1], "device": r[2], "allowed": bool(r[3]), "reason": r[4], "ts": r[5]}
            for r in rows]


# ---- TOTP (RFC 6238): encrypted seeds, 30s codes for autofill ----
def totp_now(key: str) -> str:
    import pyotp
    seed = secret_fill(key)
    return pyotp.TOTP(seed).now()


# ---- DPAPI: bind the Fernet master key to this Windows login (TPM-backed) ----
def dpapi_wrap_key() -> dict:
    """Encrypt OSOKAI_VAULT_KEY with Windows DPAPI (user scope, TPM-backed) into vault_key.dpapi."""
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    raw = os.getenv("OSOKAI_VAULT_KEY", "").encode()
    if not raw:
        return {"ok": False, "error": "OSOKAI_VAULT_KEY missing"}
    buf_in = DATA_BLOB(len(raw), (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw))
    buf_out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(buf_in), None, None, None, None, 1, ctypes.byref(buf_out)):  # 1 = UI forbidden
        return {"ok": False, "error": "DPAPI protect failed"}
    blob = bytes(buf_out.pbData[i] for i in range(buf_out.cbData))
    ctypes.windll.kernel32.LocalFree(buf_out.pbData)
    fp = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "vault_key.dpapi"))
    open(fp, "wb").write(blob)
    return {"ok": True, "file": "vault_key.dpapi", "bytes": len(blob)}
