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
    try:
        from app.paths import safe_join as _sj
    except ImportError:
        from paths import safe_join as _sj
    if parts:
        return _sj(*parts[1:], root=parts[0])
    return _sj()


MAX_IMPORT_FILES, MAX_IMPORT_BYTES = 200, 50 * 1024 * 1024


def export_bundle(paths, note: str = "") -> dict:
    """Zip + encrypt with a fresh random 256-bit key. Filename carries only a
    random ID — the key travels separately (never derivable from the file)."""
    os.makedirs(SHARED, exist_ok=True)
    key = Fernet.generate_key()
    bid = "".join(secrets.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(8))
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
    token = Fernet(key).encrypt(buf.getvalue())
    fname = f"osokai-{bid}.zip.enc"
    open(os.path.join(SHARED, fname), "wb").write(token)
    return {"ok": True, "key": key.decode(), "file": f"shared/{fname}"}


def import_bundle(filename: str, content_b64: str, key: str = "", code: str = "") -> dict:
    """Decrypt with the separate key, extract sanitized relatives into inbox/.
    Legacy 6-char codes are rejected (re-export under the new scheme)."""
    if code and not key:
        return {"ok": False, "error": "legacy share codes retired — ask sender to re-export"}
    try:
        raw = base64.b64decode(content_b64.encode())
    except Exception:
        return {"ok": False, "error": "bad base64"}
    try:
        data = Fernet(key.encode()).decrypt(raw)
    except Exception:
        return {"ok": False, "error": "wrong key or corrupted bundle"}
    os.makedirs(INBOX, exist_ok=True)
    names, total = [], 0
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except Exception:
        return {"ok": False, "error": "not a bundle"}
    for n in zf.namelist():
        rel = (n or "").replace("\\", "/").lstrip("/")
        if not rel or rel.startswith(("/", "..")) or ".." in rel.split("/") or ":" in rel.split("/")[0]:
            continue
        if n.endswith("/"):
            continue
        if len(names) >= MAX_IMPORT_FILES:
            break
        blob = zf.read(n)
        total += len(blob)
        if total > MAX_IMPORT_BYTES:
            break
        try:
            out = _safe_join(INBOX, rel)
        except ValueError:
            continue
        os.makedirs(os.path.dirname(out) or INBOX, exist_ok=True)
        with open(out, "wb") as f:
            f.write(blob)
        names.append(rel)
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
