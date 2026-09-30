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
    from app.paths import ws as _pws
except ImportError:
    from paths import ws as _pws

WS = _pws()

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


# ---- public share links: read-only goal/progress pages, signed + revocable ----
def _ldb():
    import sqlite3 as _s
    import time as _t
    try:
        from app.paths import data as _pd
    except ImportError:
        from paths import data as _pd
    db = _s.connect(os.path.normpath(_pd("osokai.db")), check_same_thread=False)
    db.execute("""CREATE TABLE IF NOT EXISTS share_links(
        token TEXT PRIMARY KEY, kind TEXT, ref INT, exp REAL, revoked INT DEFAULT 0, ts REAL)""")
    return db


def create_link(kind: str, ref: int, ttl_hours: float = 72) -> dict:
    """Capability URL token. Unguessable, expiring, revocable. No auth needed to VIEW."""
    import time as _t
    if kind not in ("goal",):
        return {"ok": False, "error": "kind must be 'goal' (for now)"}
    token = secrets.token_urlsafe(24)
    db = _ldb()
    db.execute("INSERT INTO share_links(token, kind, ref, exp, ts) VALUES(?,?,?,?,?)",
               (token, kind, ref, _t.time() + ttl_hours * 3600, _t.time()))
    db.commit()
    return {"ok": True, "token": token, "url": f"/s/{token}", "expires_in_h": ttl_hours}


def resolve_link(token: str):
    import time as _t
    r = _ldb().execute("SELECT kind, ref, exp, revoked FROM share_links WHERE token=?", (token,)).fetchone()
    if not r or r[3] or r[2] < _t.time():
        return None
    return {"kind": r[0], "ref": r[1]}


def list_links():
    rows = _ldb().execute("SELECT token, kind, ref, exp, revoked, ts FROM share_links ORDER BY ts DESC").fetchall()
    return [{"token": r[0][:8] + "…", "kind": r[1], "ref": r[2], "exp": r[3],
             "revoked": bool(r[4]), "ts": r[5]} for r in rows]


def revoke_link(token_prefix_or_full: str) -> dict:
    db = _ldb()
    if len(token_prefix_or_full) > 12:
        db.execute("UPDATE share_links SET revoked=1 WHERE token=?", (token_prefix_or_full,))
    else:
        db.execute("UPDATE share_links SET revoked=1 WHERE token LIKE ?", (token_prefix_or_full + "%",))
    db.commit()
    return {"ok": True}


def render_goal_page(gid: int) -> str:
    """Read-only progress page HTML. No actions, no secrets, no auth."""
    try:
        try:
            from app import goaltrees as _gt
        except ImportError:
            import goaltrees as _gt
        t = _gt.get_tree(gid)
    except Exception:
        t = None
    if not t:
        return "<h1>Goal not found or link expired</h1>"
    import html as _h
    parts = [f"<h1>🎯 {_h.escape(t['title'])}</h1><p>{t['progress']}% complete</p>"]
    for o in t["objectives"]:
        parts.append(f"<h2>{_h.escape(o['title'])} — {o['done']}/{o['total']}</h2><ul>")
        for p in o["projects"]:
            for task in p["tasks"]:
                mark = "✅" if task["status"] == "done" else ("🔄" if task["status"] == "doing" else "⬜")
                parts.append(f"<li>{mark} {_h.escape(task['title'])}</li>")
        parts.append("</ul>")
    parts.append("<hr><small>Shared read-only via Osok-AI</small>")
    return "\n".join(parts)
