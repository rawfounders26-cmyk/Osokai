"""Razorpay connector — our own design. Orders + UPI collect links for the
merchant wedge. Credentials from connector store or env (RAZORPAY_KEY_ID +
RAZORPAY_KEY_SECRET). Everything money-moving stays approval-gated upstream;
this module only talks to the API. Mock-tested without credentials.
"""
import os

API = "https://api.razorpay.com/v1"


def _creds():
    try:
        try:
            from app.connectors import _load
            from app.vault import decrypt
        except ImportError:
            from connectors import _load
            from vault import decrypt
        entry = (_load() or {}).get("razorpay", {})
        if entry.get("enc"):
            import json as _j
            try:
                d = _j.loads(decrypt(entry["enc"]))
                if d.get("key_id") and d.get("secret"):
                    return d["key_id"], d["secret"]
            except Exception:
                pass
    except Exception:
        pass
    kid, sec = os.getenv("RAZORPAY_KEY_ID", ""), os.getenv("RAZORPAY_KEY_SECRET", "")
    return (kid, sec) if kid and sec else (None, None)


def _auth():
    kid, sec = _creds()
    if not kid:
        return None
    import base64 as _b
    return "Basic " + _b.b64encode(f"{kid}:{sec}".encode()).decode()


def create_order(amount_inr: float, receipt: str = "", notes: dict = None) -> dict:
    """Create a Razorpay order (amount in INR). Returns order id + amount."""
    try:
        amount_paise = int(round(float(amount_inr) * 100))
    except Exception:
        return {"ok": False, "error": "bad amount"}
    if amount_paise <= 0:
        return {"ok": False, "error": "amount must be positive"}
    auth = _auth()
    if not auth:
        return {"ok": False, "error": "no Razorpay creds: paste key pair via /connectors/razorpay/connect or set RAZORPAY_KEY_ID/SECRET"}
    try:
        from app.transport import call as _tcall
    except ImportError:
        from transport import call as _tcall
    import time as _t
    r = _tcall("razorpay", "POST", f"{API}/orders", headers={"Authorization": auth},
               json_body={"amount": amount_paise, "currency": "INR",
                          "receipt": (receipt or f"osokai-{int(_t.time())}")[:40],
                          "notes": notes or {}})
    if not r.get("ok"):
        return r
    d = r.get("data", {}) or {}
    if not d.get("id"):
        return {"ok": False, "error": "razorpay accepted but returned no order id"}
    return {"ok": True, "order_id": d["id"], "amount_inr": amount_paise / 100,
            "status": d.get("status", "")}


def order_status(order_id: str) -> dict:
    auth = _auth()
    if not auth:
        return {"ok": False, "error": "no Razorpay creds"}
    try:
        from app.transport import cached_get
    except ImportError:
        from transport import cached_get
    r = cached_get("razorpay", f"order:{order_id}", f"{API}/orders/{order_id}",
                   headers={"Authorization": auth}, ttl=60)
    if not r.get("ok"):
        return r
    d = r.get("data", {}) or {}
    return {"ok": True, "order_id": d.get("id", ""), "status": d.get("status", ""),
            "amount_paid_inr": (d.get("amount_paid", 0) or 0) / 100,
            "cached": r.get("cached", False)}


def collect_link(amount_inr: float, upi_id: str, note: str = "") -> dict:
    """No-creds fallback: plain UPI intent link (works today, no account needed)."""
    try:
        from app.bills import upi_link
    except ImportError:
        from bills import upi_link
    if not upi_id or "@" not in upi_id:
        return {"ok": False, "error": "valid UPI id required"}
    try:
        amt = float(amount_inr)
        if amt <= 0:
            return {"ok": False, "error": "amount must be positive"}
    except Exception:
        return {"ok": False, "error": "bad amount"}
    return {"ok": True, "upi": upi_link(upi_id.strip(), "Osok-AI", amt, note or "OsokAI collect")}
