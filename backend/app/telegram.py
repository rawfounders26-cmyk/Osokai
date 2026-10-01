"""Telegram connector — our own design. Texting interface for the agent.

Outbound: send_message (approval-gated publishes reuse the dispatcher).
Inbound: long-poll worker maps incoming messages to chat turns (opt-in per
chat via /telegram/poll, offset persisted). Tokens in vault, never logged.
"""
import os
import time

try:
    from app.db import connect as _hardb
    from app.paths import data as _pdata
except ImportError:
    from db import connect as _hardb
    from paths import data as _pdata

DB = _pdata("osokai.db")
API = "https://api.telegram.org/bot"


def _db():
    db = _hardb(os.path.normpath(DB))
    db.execute("""CREATE TABLE IF NOT EXISTS telegram_chats(
        chat_id TEXT PRIMARY KEY, enabled INT DEFAULT 1, offset INT DEFAULT 0, ts REAL)""")
    return db


def _token() -> str:
    try:
        try:
            from app.connectors import _load
            from app.vault import decrypt
        except ImportError:
            from connectors import _load
            from vault import decrypt
        entry = (_load() or {}).get("telegram", {})
        if entry.get("enc"):
            try:
                tok = decrypt(entry["enc"])
                if tok:
                    return tok
            except Exception:
                pass
    except Exception:
        pass
    return os.getenv("TELEGRAM_BOT_TOKEN", "")


def _call(method: str, payload: dict):
    import httpx as _hx
    tok = _token()
    if not tok:
        return {"ok": False, "error": "no Telegram token: paste bot token via /connectors/telegram/connect"}
    try:
        r = _hx.post(f"{API}{tok}/{method}", json=payload, timeout=30)
        d = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code != 200 or d.get("ok") is not True:
            return {"ok": False, "error": f"telegram rejected: {r.status_code} {(d.get('description') or r.text)[:150]}"}
        return {"ok": True, "result": d.get("result", {})}
    except Exception as e:
        return {"ok": False, "error": f"telegram call failed: {e}"[:200]}


def send(chat_id: str, text: str) -> dict:
    """Outbound message. Callers gate via dispatcher; this function just sends."""
    chat_id, text = (chat_id or "").strip(), (text or "").strip()
    if not chat_id or not text:
        return {"ok": False, "error": "chat_id + text required"}
    if len(text) > 4000:
        return {"ok": False, "error": "message too long (>4000 chars)"}
    return _call("sendMessage", {"chat_id": chat_id, "text": text[:4000]})


def enable_chat(chat_id: str, enabled: bool = True) -> dict:
    db = _db()
    db.execute("INSERT OR REPLACE INTO telegram_chats(chat_id, enabled, ts) VALUES(?,?,?)",
               (str(chat_id), 1 if enabled else 0, time.time()))
    db.commit()
    return {"ok": True}


def poll_once() -> dict:
    """One inbound sweep: new messages in enabled chats become chat turns.
    Returns count ingested. Never raises."""
    db = _db()
    chats = [r[0] for r in db.execute("SELECT chat_id FROM telegram_chats WHERE enabled=1").fetchall()]
    if not chats:
        return {"ok": True, "ingested": 0}
    try:
        try:
            from app.memory import Memory
        except ImportError:
            from memory import Memory
        mem = Memory()
    except Exception:
        return {"ok": False, "error": "no memory"}
    total = 0
    for cid in chats:
        row = db.execute("SELECT offset FROM telegram_chats WHERE chat_id=?", (cid,)).fetchone()
        off = row[0] if row else 0
        r = _call("getUpdates", {"offset": off, "timeout": 0, "limit": 20})
        if not r.get("ok"):
            continue
        for u in r.get("result", []) or []:
            uid = u.get("update_id", 0)
            msg = u.get("message") or {}
            text = (msg.get("text") or "").strip()
            if text and str((msg.get("chat") or {}).get("id", "")) == str(cid):
                mem.add("user", f"[telegram] {text[:1000]}")
                total += 1
            db.execute("UPDATE telegram_chats SET offset=? WHERE chat_id=?", (uid + 1, cid))
        db.commit()
    return {"ok": True, "ingested": total}
