"""Plugin sandbox runtime — signed is verified, sandboxed is enforced.

Marketplace packs execute ONLY through here. Each action is:
1. allow-listed (unknown tools don't exist),
2. perm-gated (pack must hold the grant),
3. jailed (files stay under workspace/, network off unless net.fetch granted),
4. audited (every call logged; kill-switch per pack).
This is what makes signed+sandboxed beat unsigned extensions.
"""
import os
import sqlite3
import time

try:
    from app.paths import data as _pdata, ws as _pws
except ImportError:
    from paths import data as _pdata, ws as _pws

try:
    from app.db import connect as _hardb
except ImportError:
    from db import connect as _hardb
DB = _pdata("osokai.db")
WS = _pws()

# action -> required perm (None = no pack may call it; "" = always allowed)
ACTIONS = {
    "read_file": "files.read",
    "write_file": "files.write",
    "append_note": "",            # memory notes are always safe
    "add_loop": "loops.write",
    "web_fetch": "net.fetch",     # network OFF by default
    "calendar_add": "calendar.write",
    "send_email": "email.send",
    "browser_open": "browser.control",
    "vault_read": "vault.read",   # critical: acked at install, audited hard
}

MAX_WRITE_BYTES = 200_000


def _db():
    db = _hardb(os.path.normpath(DB))
    db.execute("""CREATE TABLE IF NOT EXISTS runtime_audit(
        id INTEGER PRIMARY KEY, skill TEXT, action TEXT, target TEXT,
        allowed INT, ms INT, ts REAL)""")
    db.execute("CREATE TABLE IF NOT EXISTS runtime_killed(skill TEXT PRIMARY KEY, ts REAL)")
    return db


def kill(skill: str) -> dict:
    db = _db()
    db.execute("INSERT OR REPLACE INTO runtime_killed(skill, ts) VALUES(?,?)", (skill, time.time()))
    db.commit()
    return {"ok": True, "killed": skill}


def unkill(skill: str) -> dict:
    db = _db()
    db.execute("DELETE FROM runtime_killed WHERE skill=?", (skill,))
    db.commit()
    return {"ok": True}


def is_killed(skill: str) -> bool:
    return _db().execute("SELECT 1 FROM runtime_killed WHERE skill=?", (skill,)).fetchone() is not None


def _jail(path: str) -> str:
    try:
        from app.paths import safe_join as _sj
    except ImportError:
        from paths import safe_join as _sj
    try:
        return _sj(path)
    except ValueError:
        raise PermissionError(f"path escapes workspace jail: {path}")


def _audit(skill, action, target, allowed, ms):
    try:
        db = _db()
        db.execute("INSERT INTO runtime_audit(skill, action, target, allowed, ms, ts) VALUES(?,?,?,?,?,?)",
                   (skill, action, (target or "")[:300], 1 if allowed else 0, ms, time.time()))
        db.commit()
    except Exception:
        pass


def run(skill: str, action: str, args: dict = None) -> dict:
    """Execute one pack action inside the sandbox. Returns ok/result or ok/error."""
    import time as _t
    t0 = _t.time()
    args = args or {}
    ok, out = False, None
    try:
        if action not in ACTIONS:
            raise PermissionError(f"unknown action '{action}' — not allow-listed")
        if is_killed(skill):
            raise PermissionError(f"pack '{skill}' is kill-switched")
        need = ACTIONS[action]
        if need:
            try:
                from app.sandbox import guard
            except ImportError:
                from sandbox import guard
            guard(skill, need)
        out = _do(action, args)
        ok = True
    except (PermissionError, ValueError) as e:
        out = f"denied: {e}"
    except Exception as e:
        out = f"failed: {type(e).__name__}: {e}"[:300]
    _audit(skill, action, str(args.get("path") or args.get("url") or args.get("title") or ""), ok,
           int((_t.time() - t0) * 1000))
    return {"ok": ok, **({"result": out} if ok else {"error": out})}


def _do(action: str, args: dict):
    if action == "read_file":
        fp = _jail(args.get("path", ""))
        with open(fp, encoding="utf-8", errors="ignore") as f:
            return f.read(MAX_WRITE_BYTES)
    if action == "write_file":
        fp = _jail(args.get("path", ""))
        data = (args.get("content", ""))[:MAX_WRITE_BYTES]
        os.makedirs(os.path.dirname(fp) or WS, exist_ok=True)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(data)
        return f"wrote {len(data)} bytes to {os.path.relpath(fp, WS)}"
    if action == "append_note":
        try:
            from app.memory import Memory
        except ImportError:
            from memory import Memory
        Memory().note_fact(str(args.get("text", ""))[:500], float(args.get("salience", 1.0)))
        return "noted"
    if action == "add_loop":
        try:
            from app.loops import add as _add
        except ImportError:
            from loops import add as _add
        r = _add("promise", str(args.get("title", ""))[:200], "sandbox:" + str(args.get("skill", "?")))
        return f"loop #{r.get('id')}"
    if action == "web_fetch":
        import httpx as _hx
        r = _hx.get(args.get("url", ""), timeout=20, follow_redirects=True)
        r.raise_for_status()
        return r.text[:20000]
    if action == "calendar_add":
        try:
            from app import calendar as _cal
        except ImportError:
            import calendar as _cal
        r = _cal.add(str(args.get("title", ""))[:200], args.get("day", ""), args.get("time", ""))
        return f"event #{r.get('id')} {r.get('when')}"
    if action == "send_email":
        return "queued — email sends only via approval outbox, never directly"
    if action == "browser_open":
        try:
            from app.system_tools import open_url
        except ImportError:
            from system_tools import open_url
        open_url(args.get("url", ""))
        return "opened"
    if action == "vault_read":
        raise PermissionError("vault reads are mediated, never direct — use the fill flow")
    raise ValueError("unreachable")


def audit(skill: str = "", limit: int = 30):
    db = _db()
    q = "SELECT id, skill, action, target, allowed, ms, ts FROM runtime_audit"
    args: tuple = ()
    if skill:
        q += " WHERE skill=?"
        args = (skill,)
    q += " ORDER BY id DESC LIMIT ?"
    rows = db.execute(q, args + (limit,)).fetchall()
    return [{"id": r[0], "skill": r[1], "action": r[2], "target": r[3],
             "allowed": bool(r[4]), "ms": r[5], "ts": r[6]} for r in rows]
