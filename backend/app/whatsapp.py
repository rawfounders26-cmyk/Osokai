"""WhatsApp Business connector — our own design. Template + text sends via the
Meta Graph API (needs WHATSAPP_TOKEN + WHATSAPP_PHONE_ID, or a pasted token).
Approval-gated sends only; inbound webhooks stay a documented next step
(polling unofficial APIs is a ban risk we don't take). Mock-tested."""
import os

API = "https://graph.facebook.com/v21.0"


def _token():
    try:
        try:
            from app.connectors import _load
            from app.vault import decrypt
        except ImportError:
            from connectors import _load
            from vault import decrypt
        entry = (_load() or {}).get("whatsapp_business", {})
        if entry.get("enc"):
            try:
                tok = decrypt(entry["enc"])
                if tok:
                    return tok
            except Exception:
                pass
    except Exception:
        pass
    return os.getenv("WHATSAPP_TOKEN", "")


def _phone_id() -> str:
    return os.getenv("WHATSAPP_PHONE_ID", "")


def send_text(to_e164: str, text: str) -> dict:
    """Send a text message. Caller gates via dispatcher; this just sends."""
    import re as _re
    to = (to_e164 or "").strip().replace(" ", "")
    if not _re.fullmatch(r"\+?\d{10,15}", to):
        return {"ok": False, "error": "bad destination (E.164 digits required)"}
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "empty message"}
    if len(text) > 4000:
        return {"ok": False, "error": "message too long (>4000 chars)"}
    tok, pid = _token(), _phone_id()
    if not tok or not pid:
        return {"ok": False, "error": "no WhatsApp creds: set WHATSAPP_TOKEN + WHATSAPP_PHONE_ID"}
    try:
        from app.transport import call as _tcall
    except ImportError:
        from transport import call as _tcall
    r = _tcall("whatsapp", "POST", f"{API}/{pid}/messages",
               headers={"Authorization": f"Bearer {tok}"},
               json_body={"messaging_product": "whatsapp", "to": to,
                          "type": "text", "text": {"body": text[:4000]}})
    if not r.get("ok"):
        return r
    d = r.get("data", {}) or {}
    msgs = d.get("messages") or []
    if not msgs:
        return {"ok": False, "error": "whatsapp accepted but returned no message id"}
    return {"ok": True, "message_id": (msgs[0] or {}).get("id", "")}
