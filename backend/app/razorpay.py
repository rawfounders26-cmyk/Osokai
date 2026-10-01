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
    import httpx as _hx
    try:
        r = _hx.post(f"{API}/orders", headers={"Authorization": auth},
                      json={"amount": amount_paise, "currency": "INR",
                            "receipt": (receipt or f"osokai-{int(__import__('time').time())}")[:40],
                            "notes": notes or {}}, timeout=30)
        d = r.json() if "json" in r.headers.get("content-type", "") else {}
        if r.status_code not in (200, 201) or not d.get("id"):
            return {"ok": False, "error": f"razorpay rejected: {r.status_code} {r.text[:150]}"}
        return {"ok": True, "order_id": d["id"], "amount_inr": amount_paise / 100,
                "status": d.get("status", "")}
    except Exception as e:
        return {"ok": False, "error": f"razorpay call failed: {e}"[:200]}


def order_status(order_id: str) -> dict:
    auth = _auth()
    if not auth:
        return {"ok": False, "error": "no Razorpay creds"}
    import httpx as _hx
    try:
        r = _hx.get(f"{API}/orders/{order_id}", headers={"Authorization": auth}, timeout=20)
        d = r.json() if r.status_code == 200 else {}
        if r.status_code != 200:
            return {"ok": False, "error": f"razorpay {r.status_code}: {r.text[:120]}"}
        return {"ok": True, "order_id": d.get("id", ""), "status": d.get("status", ""),
                "amount_paid_inr": (d.get("amount_paid", 0) or 0) / 100}
    except Exception as e:
        return {"ok": False, "error": f"razorpay call failed: {e}"[:200]}


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
