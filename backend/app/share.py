"""Trusted sharing — osokai-to-Osok-AI file handoff, local-first.
Export: zips workspace paths, Fernet-encrypts with a short share code, drops the
bundle in workspace/shared/. Tell the code + file to your contact (any channel);
their Osok-AI imports it. No server, no account, in either direction."""
import base64
import hashlib
import io
import os
import secrets
import zipfile

from cryptography.fernet import Fernet

try:
    WS = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "workspace"))
except Exception:
    WS = "workspace"

SHARED = os.path.join(WS, "shared")
INBOX = os.path.join(WS, "inbox")


def _key_for(code: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256(("osokai-share:" + code).encode()).digest())


def _safe_join(*parts: str) -> str:
    fp = os.path.normpath(os.path.join(*parts))
    if not fp.startswith(WS):
        raise ValueError("path escapes workspace")
    return fp


def export_bundle(paths, note: str = "") -> dict:
    """Zip + encrypt. Returns share code + bundle filename."""
    os.makedirs(SHARED, exist_ok=True)
    code = "".join(secrets.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(6))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("osokai-note.txt", note or "")
        for p in paths or []:
            fp = _safe_join(WS, p)
            if os.path.isfile(fp):
                z.write(fp, os.path.basename(fp))
            elif os.path.isdir(fp):
                for root, _, files in os.walk(fp):
                    for f in files:
                        full = os.path.join(root, f)
                        z.write(full, os.path.relpath(full, WS))
    token = Fernet(_key_for(code)).encrypt(buf.getvalue())
    fname = f"osokai-{code}.zip.enc"
    open(os.path.join(SHARED, fname), "wb").write(token)
    return {"ok": True, "code": code, "file": f"shared/{fname}"}


def import_bundle(filename: str, content_b64: str, code: str) -> dict:
    """Decrypt with the share code, extract into workspace/inbox/."""
    raw = base64.b64decode(content_b64.encode())
    try:
        data = Fernet(_key_for(code)).decrypt(raw)
    except Exception:
        return {"ok": False, "error": "wrong code or corrupted bundle"}
    os.makedirs(INBOX, exist_ok=True)
    names = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for n in z.namelist():
            if n.startswith("/") or ".." in n:
                continue
            out = _safe_join(INBOX, os.path.basename(n)) if "/" not in n.rstrip("/") else None
            if out is None:
                continue
            with open(out, "wb") as f:
                f.write(z.read(n))
            names.append(os.path.basename(n))
    return {"ok": True, "imported": names, "into": "inbox/"}


def list_shared():
    os.makedirs(SHARED, exist_ok=True)
    return sorted(f for f in os.listdir(SHARED) if f.endswith(".zip.enc"))
