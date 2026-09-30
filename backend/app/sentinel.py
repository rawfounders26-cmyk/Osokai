"""Sentinel gate — ask before sensitive actions (Muse-style, local)."""
SENSITIVE = ["send email", "delete", "format", "payment", "buy ", "order ", "pay ", "whatsapp send", "post to"]

def needs_approval(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in SENSITIVE)
