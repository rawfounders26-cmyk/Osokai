"""Client-held E2E — true end-to-end graduation of relay-lite.

Devices generate X25519 keypairs LOCALLY; the server stores PUBLIC keys only
and relays envelopes it can never open. Seal/open helpers live here for
clients (and tests); the server endpoints only store + forward ciphertext.

Envelope v2: {v:2, from, eph_pub, ct} where ct = Fernet(ECDH(eph, recipient)).
  (confidential only — sender claim unverified; kept for compat)
Envelope v3: v2 + {id_pub, sig} where sig = Ed25519(canonical inner) by the
  sender's identity key. open_envelope verifies before trusting `from`.
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

try:
    from app.db import connect as _hardb
except ImportError:
    from db import connect as _hardb
DB = _pdata("osokai.db")


def _db():
    db = _hardb(os.path.normpath(DB))
    db.execute("CREATE TABLE IF NOT EXISTS e2e_devices(device TEXT PRIMARY KEY, pubkey TEXT, ts REAL)")
    try:
        db.execute("ALTER TABLE e2e_devices ADD COLUMN id_pub TEXT DEFAULT ''")
    except Exception:
        pass
    db.execute("""CREATE TABLE IF NOT EXISTS e2e_inbox(
        id INTEGER PRIMARY KEY, device TEXT, envelope TEXT, ts REAL, delivered INTEGER DEFAULT 0)""")
    return db


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode()


def _ub(s: str) -> bytes:
    return base64.urlsafe_b64decode(s.encode())


def _valid_raw_key(s: str) -> bool:
    try:
        return len(_ub(s)) == 32
    except Exception:
        return False


def generate_identity() -> dict:
    """Client-side Ed25519 identity keypair for sender authentication.
    Separate from the X25519 encryption keys: confidentiality ≠ identity."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    priv = Ed25519PrivateKey.generate()
    raw_priv = priv.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                  serialization.NoEncryption())
    raw_pub = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return {"private": _b64(raw_priv), "public": _b64(raw_pub)}


def _canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


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


def seal_to(sender_priv_b64: str, recipient_pub_b64: str, sender: str, payload: dict,
            sender_sign_priv_b64: str = "") -> dict:
    """Seal to recipient. Pass sender_sign_priv_b64 for a v3 signed envelope
    (sender claim verifiable); without it you get a v2 confidential-only envelope."""
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    from cryptography.hazmat.primitives import serialization
    s_priv = X25519PrivateKey.from_private_bytes(_ub(sender_priv_b64))
    r_pub = X25519PublicKey.from_public_bytes(_ub(recipient_pub_b64))
    eph = X25519PrivateKey.generate()
    shared = eph.exchange(r_pub)
    f = Fernet(_derive(shared))
    eph_pub = eph.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    inner = {"from": sender, "payload": payload}
    env = {"v": 2, "from": sender, "eph_pub": _b64(eph_pub), "ct": f.encrypt(_canonical(inner)).decode()}
    if sender_sign_priv_b64:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        sp = Ed25519PrivateKey.from_private_bytes(_ub(sender_sign_priv_b64))
        env["v"] = 3
        env["id_pub"] = _b64(sp.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw))
        env["sig"] = _b64(sp.sign(_canonical(inner)))
    return env


def open_envelope(recipient_priv_b64: str, env: dict, expected_id_pub: str = "") -> dict:
    """Decrypt + (v3) verify sender signature. `from` is trusted ONLY when
    sender_authenticated is True. raises on bad signature / version."""
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    if env.get("v") not in (2, 3):
        raise ValueError("unsupported envelope version")
    r_priv = X25519PrivateKey.from_private_bytes(_ub(recipient_priv_b64))
    eph_pub = X25519PublicKey.from_public_bytes(_ub(env["eph_pub"]))
    f = Fernet(_derive(r_priv.exchange(eph_pub)))
    inner = json.loads(f.decrypt(env["ct"].encode()).decode())
    if env.get("v") == 2:
        return {"from": inner.get("from", ""), "payload": inner.get("payload"),
                "sender_authenticated": False}
    # v3: signature MUST verify or the envelope is rejected outright
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
    id_pub = expected_id_pub or env.get("id_pub", "")
    if not _valid_raw_key(id_pub):
        raise ValueError("v3 envelope without valid identity key")
    try:
        Ed25519PublicKey.from_public_bytes(_ub(id_pub)).verify(
            _ub(env.get("sig", "")), _canonical({"from": inner.get("from"), "payload": inner.get("payload")}))
    except InvalidSignature:
        raise ValueError("sender signature invalid — claimed identity rejected")
    if expected_id_pub and id_pub != expected_id_pub:
        raise ValueError("identity key mismatch (possible impersonation)")
    return {"from": inner.get("from", ""), "payload": inner.get("payload"),
            "sender_authenticated": True}


# ---- server side: public-key directory + blind relay (never decrypts) ----
def register(device: str, pubkey: str, id_pub: str = "", replace: bool = False) -> dict:
    if not _valid_raw_key(pubkey):
        return {"ok": False, "error": "bad pubkey (must decode to 32 bytes)"}
    if id_pub and not _valid_raw_key(id_pub):
        return {"ok": False, "error": "bad identity key (must decode to 32 bytes)"}
    db = _db()
    row = db.execute("SELECT pubkey FROM e2e_devices WHERE device=?", (device,)).fetchone()
    if row and row[0] != pubkey and not replace:
        return {"ok": False, "error": "device key changed — re-enroll explicitly with replace=true"}
    db.execute("INSERT OR REPLACE INTO e2e_devices(device, pubkey, id_pub, ts) VALUES(?,?,?,?)",
               (device, pubkey, id_pub, time.time()))
    db.commit()
    return {"ok": True}


def directory():
    return [{"device": r[0], "pubkey": r[1], "id_pub": r[2] if len(r) > 2 else ""} for r in
            _db().execute("SELECT device, pubkey, id_pub FROM e2e_devices ORDER BY device").fetchall()]


def push_envelope(device: str, envelope: dict) -> dict:
    if not isinstance(envelope, dict) or envelope.get("v") not in (2, 3):
        return {"ok": False, "error": "v2/v3 envelope required"}
    if not envelope.get("eph_pub") or not envelope.get("ct"):
        return {"ok": False, "error": "malformed envelope"}
    if envelope.get("v") == 3 and not envelope.get("sig"):
        return {"ok": False, "error": "v3 envelope without signature"}
    db = _db()
    cur = db.execute("INSERT INTO e2e_inbox(device, envelope, ts) VALUES(?,?,?)",
                     (device, json.dumps(envelope)[:8000], time.time()))
    db.commit()
    return {"ok": True, "id": cur.lastrowid}


def pull_envelopes(device: str, limit: int = 20):
    """Read-only fetch. Clients ack received IDs separately — crashes lose nothing."""
    db = _db()
    rows = db.execute("SELECT id, envelope, ts FROM e2e_inbox WHERE device=? AND delivered=0 ORDER BY id LIMIT ?",
                      (device, max(1, min(100, limit)))).fetchall()
    out = []
    for r in rows:
        try:
            env = json.loads(r[1])
        except Exception:
            continue  # quarantine malformed legacy rows
        out.append({"id": r[0], "envelope": env, "ts": r[2]})
    return out


def ack_envelopes(device: str, ids) -> dict:
    try:
        clean = [int(i) for i in (ids or [])]
    except Exception:
        return {"ok": False, "error": "ids must be integers"}
    if not clean:
        return {"ok": True, "acked": 0}
    db = _db()
    cur = db.execute(f"UPDATE e2e_inbox SET delivered=1 WHERE device=? AND delivered=0 AND id IN ({','.join('?' * len(clean))})",
                     (device, *clean))
    db.commit()
    return {"ok": True, "acked": cur.rowcount}
