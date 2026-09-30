"""Email outbox — compose → approve → queue. Sends via Gmail API the moment
OAuth is live; until then it queues honestly with status 'queued-no-oauth'."""
import os
import sqlite3
import time

DB = os.path.join(os.path.dirname(__file__), "..", "osokai.db")

def _db():
    db = sqlite3.connect(os.path.normpath(DB), check_same_thread=False)
    db.execute("""CREATE TABLE IF NOT EXISTS email_outbox(
        id INTEGER PRIMARY KEY, to_addr TEXT, subject TEXT, body TEXT,
        status TEXT, ts REAL, sent_ts REAL DEFAULT 0)""")
    return db

def compose(to_addr: str, subject: str, body: str):
    db = _db()
    cur = db.execute("INSERT INTO email_outbox(to_addr, subject, body, status, ts) VALUES(?,?,?,?,?)",
                     (to_addr, subject, body, "pending-approval", time.time()))
    db.commit()
    return {"ok": True, "id": cur.lastrowid, "status": "pending-approval"}

def approve(eid: int):
    """Approve -> try live Gmail send, else queue honestly."""
    db = _db()
    r = db.execute("SELECT to_addr, subject, body FROM email_outbox WHERE id=?", (eid,)).fetchone()
    if not r:
        return {"ok": False, "error": "not found"}
    sent, detail = _try_gmail_send(r[0], r[1], r[2])
    status = "sent" if sent else "queued-no-oauth"
    db.execute("UPDATE email_outbox SET status=?, sent_ts=? WHERE id=?",
               (status, time.time() if sent else 0, eid))
    db.commit()
    return {"ok": True, "id": eid, "status": status, "detail": detail}

def outbox():
    db = _db()
    return [{"id": r[0], "to": r[1], "subject": r[2], "status": r[3], "ts": r[4]}
            for r in db.execute("SELECT id, to_addr, subject, status, ts FROM email_outbox ORDER BY id DESC LIMIT 30")]

def _try_gmail_send(to_addr: str, subject: str, body: str):
    """Returns (sent_bool, detail). Needs oauth_gmail token in vault."""
    try:
        from app.connectors import _load
    except ImportError:
        from connectors import _load
    tok = (_load().get("gmail") or {}).get("oauth_enc", "")
    if not tok:
        return False, "no Gmail OAuth yet — connect via /connectors/gmail/login"
    try:
        import json as _j
        try:
            from app.vault import decrypt
        except ImportError:
            from vault import decrypt
        import base64
        import httpx
        access = _j.loads(decrypt(tok)).get("access_token", "")
        raw = base64.urlsafe_b64encode(f"To: {to_addr}\r\nSubject: {subject}\r\n\r\n{body}".encode()).decode()
        r = httpx.post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                       headers={"Authorization": f"Bearer {access}"}, json={"raw": raw}, timeout=30)
        if r.status_code == 200:
            return True, "sent via Gmail"
        return False, f"gmail API {r.status_code}"
    except Exception as e:
        return False, str(e)[:150]

def parse_compose(text: str):
    """'send email to ravi about dinner tomorrow' -> (to, subject, body)."""
    import re
    m = re.match(r"^send email to\s+(.+?)\s+about\s+(.+)$", text.strip(), re.I)
    if not m:
        return None
    return m.group(1).strip(), m.group(2).strip(), m.group(2).strip()
