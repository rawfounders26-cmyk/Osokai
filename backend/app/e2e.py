"""Client-held E2E — true end-to-end graduation of relay-lite.

Devices generate X25519 keypairs LOCALLY; the server stores PUBLIC keys only
and relays envelopes it can never open. Seal/open helpers live here for
clients (and tests); the server endpoints only store + forward ciphertext.

Envelope v2: {v:2, from, eph_pub, ct} where ct = Fernet(ECDH(eph, recipient)).
Relay-lite v1 envelopes keep working untouched.
"""
import base64
import json
import os
import sqlite3
import time

try:
    from app.paths import data as _pdata
except ImportError:
    from paths import data as _pdata

DB = _pdata("osokai.db")


def _db():
    db = sqlite3.connect(os.path.normpath(DB), check_same_thread=False)
    db.execute("CREATE TABLE IF NOT EXISTS e2e_devices(device TEXT PRIMARY KEY, pubkey TEXT, ts REAL)")
    db.execute("""CREATE TABLE IF NOT EXISTS e2e_inbox(
        id INTEGER PRIMARY KEY, device TEXT, envelope TEXT, ts REAL, delivered INTEGER DEFAULT 0)""")
    return db


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode()


def _ub(s: str) -> bytes:
    return base64.urlsafe_b64decode(s.encode())


def generate_keypair() -> dict:
    """Client-side: returns {private, public} raw-b64 X25519 keys. Private never leaves the device."""
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    priv = X25519PrivateKey.generate()
    pub = priv.public_key()
    raw_priv = priv.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                  serialization.NoEncryption())
    raw_pub = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return {"private": _b64(raw_priv), "public": _b64(raw_pub)}


def _derive(shared: bytes) -> bytes:
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives import hashes
    return _b64(HKDF(algorithm=hashes.SHA256(), length=32, salt=b"osokai-e2e-v2", info=b"envelope").derive(shared)).encode()


def seal_to(sender_priv_b64: str, recipient_pub_b64: str, sender: str, payload: dict) -> dict:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    from cryptography.hazmat.primitives import serialization
    s_priv = X25519PrivateKey.from_private_bytes(_ub(sender_priv_b64))
    r_pub = X25519PublicKey.from_public_bytes(_ub(recipient_pub_b64))
    eph = X25519PrivateKey.generate()
    shared = eph.exchange(r_pub)
    f = Fernet(_derive(shared))
    eph_pub = eph.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    inner = json.dumps({"from": sender, "payload": payload}).encode()
    return {"v": 2, "from": sender, "eph_pub": _b64(eph_pub), "ct": f.encrypt(inner).decode()}


def open_envelope(recipient_priv_b64: str, env: dict) -> dict:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    if env.get("v") != 2:
        raise ValueError("not a v2 envelope")
    r_priv = X25519PrivateKey.from_private_bytes(_ub(recipient_priv_b64))
    eph_pub = X25519PublicKey.from_public_bytes(_ub(env["eph_pub"]))
    f = Fernet(_derive(r_priv.exchange(eph_pub)))
    return json.loads(f.decrypt(env["ct"].encode()).decode())


# ---- server side: public-key directory + blind relay (never decrypts) ----
def register(device: str, pubkey: str) -> dict:
    try:
        _ub(pubkey)
    except Exception:
        return {"ok": False, "error": "bad pubkey"}
    db = _db()
    db.execute("INSERT OR REPLACE INTO e2e_devices(device, pubkey, ts) VALUES(?,?,?)",
               (device, pubkey, time.time()))
    db.commit()
    return {"ok": True}


def directory():
    return [{"device": r[0], "pubkey": r[1]} for r in
            _db().execute("SELECT device, pubkey FROM e2e_devices ORDER BY device").fetchall()]


def push_envelope(device: str, envelope: dict) -> dict:
    if not isinstance(envelope, dict) or envelope.get("v") != 2:
        return {"ok": False, "error": "v2 envelope required"}
    db = _db()
    cur = db.execute("INSERT INTO e2e_inbox(device, envelope, ts) VALUES(?,?,?)",
                     (device, json.dumps(envelope)[:8000], time.time()))
    db.commit()
    return {"ok": True, "id": cur.lastrowid}


def pull_envelopes(device: str, limit: int = 20):
    db = _db()
    rows = db.execute("SELECT id, envelope, ts FROM e2e_inbox WHERE device=? AND delivered=0 ORDER BY id LIMIT ?",
                      (device, limit)).fetchall()
    out = [{"id": r[0], "envelope": json.loads(r[1]), "ts": r[2]} for r in rows]
    if rows:
        db.execute("UPDATE e2e_inbox SET delivered=1 WHERE device=? AND delivered=0", (device,))
        db.commit()
    return out
