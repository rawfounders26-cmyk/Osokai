"""E2E relay-lite — store-and-forward sealed envelopes.

Payloads are Fernet-sealed with a relay key derived from the server auth
token, so the relay store holds ciphertext only. Clients pull by device and
unseal locally. Honest scope: transport-sealed relay (step 1); true E2E with
client-held keys rides the same envelope format later.
"""
import base64
import hashlib
import json
import os
import sqlite3
import time

try:
    from app.paths import data as _pdata
except ImportError:
    from paths import data as _pdata

DB = _pdata("osokai.db")
TTL = 7 * 86400


def _key() -> bytes:
    from cryptography.fernet import Fernet
    raw = hashlib.sha256((os.getenv("OSOKAI_AUTH_TOKEN", "osokai-dev") + ":relay").encode()).digest()
    return base64.urlsafe_b64encode(raw)


def _db():
    db = sqlite3.connect(os.path.normpath(DB), check_same_thread=False)
    db.execute("""CREATE TABLE IF NOT EXISTS relay_inbox(
        id INTEGER PRIMARY KEY, device TEXT, envelope TEXT, ts REAL, delivered INTEGER DEFAULT 0)""")
    return db


def seal(device: str, payload: dict) -> dict:
    from cryptography.fernet import Fernet
    f = Fernet(_key())
    ct = f.encrypt(json.dumps(payload)[:8000].encode()).decode()
    db = _db()
    cur = db.execute("INSERT INTO relay_inbox(device, envelope, ts) VALUES(?,?,?)", (device, ct, time.time()))
    db.commit()
    return {"ok": True, "id": cur.lastrowid}


def unseal(ct: str) -> dict:
    from cryptography.fernet import Fernet
    return json.loads(Fernet(_key()).decrypt(ct.encode()).decode())


def pull(device: str, limit: int = 20):
    """Return sealed envelopes (still encrypted) + mark delivered. Server never decrypts."""
    db = _db()
    db.execute("DELETE FROM relay_inbox WHERE ts<?", (time.time() - TTL,))
    rows = db.execute("SELECT id, envelope, ts FROM relay_inbox WHERE device=? AND delivered=0 ORDER BY id LIMIT ?",
                      (device, limit)).fetchall()
    out = [{"id": r[0], "envelope": r[1], "ts": r[2]} for r in rows]
    if rows:
        db.execute("UPDATE relay_inbox SET delivered=1 WHERE device=? AND delivered=0", (device,))
        db.commit()
    return out


def pending_count(device: str) -> int:
    db = _db()
    r = db.execute("SELECT COUNT(*) FROM relay_inbox WHERE device=? AND delivered=0", (device,)).fetchone()
    return r[0] if r else 0
