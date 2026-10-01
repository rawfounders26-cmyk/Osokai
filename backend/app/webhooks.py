"""Inbound webhooks — providers talk back. Signature-verified, then normalized
into the event bus. No signature, no event: unauthenticated POSTs never become
facts in the agent's world."""
import hashlib
import hmac
import json
import os


def _secret(provider: str) -> str:
    try:
        try:
            from app.connectors import _load
            from app.vault import decrypt
        except ImportError:
            from connectors import _load
            from vault import decrypt
        entry = (_load() or {}).get(provider, {})
        if entry.get("enc"):
            try:
                tok = decrypt(entry["enc"])
                if tok:
                    return tok
            except Exception:
                pass
    except Exception:
        pass
    return os.getenv(f"{provider.upper()}_WEBHOOK_SECRET", "")


def verify(provider: str, raw: bytes, headers: dict) -> dict:
    """Verify provider signature. Returns {ok, reason}."""
    provider = (provider or "").lower()
    hdrs = {str(k).lower(): v for k, v in (headers or {}).items()}
    if provider == "github":
        sig = hdrs.get("x-hub-signature-256", "")
        secret = _secret("github")
        if not secret:
            return {"ok": False, "reason": "no webhook secret configured"}
        if not sig.startswith("sha256="):
            return {"ok": False, "reason": "missing signature"}
        good = hmac.compare_digest(
            "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest(), sig)
        return {"ok": good, "reason": "" if good else "bad signature"}
    if provider == "telegram":
        secret = _secret("telegram")
        got = hdrs.get("x-telegram-bot-api-secret-token", "")
        if not secret:
            return {"ok": False, "reason": "no webhook secret configured"}
        ok = bool(got) and hmac.compare_digest(got, secret)
        return {"ok": ok, "reason": "" if ok else "bad token"}
    # generic HMAC: X-Signature header over raw body
    secret = _secret(provider)
    if not secret:
        return {"ok": False, "reason": f"no webhook secret for '{provider}'"}
    got = hdrs.get("x-signature", "")
    ok = bool(got) and hmac.compare_digest(
        hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest(), got)
    return {"ok": ok, "reason": "" if ok else "bad signature"}


def ingest(provider: str, payload: dict) -> dict:
    """Verified payload -> normalized bus event. Never raises."""
    try:
        try:
            from app.context.events import emit
        except ImportError:
            from context.events import emit
        summary = ""
        etype = f"{provider}.webhook" if provider in ("github", "telegram") else "connector.webhook"
        if provider == "github":
            action = str(payload.get("action", ""))
            repo = ((payload.get("repository") or {}).get("full_name", "") or "")[:120]
            summary = f"github {action} on {repo}"[:200]
        elif provider == "telegram":
            msg = payload.get("message") or {}
            summary = str(msg.get("text", ""))[:200]
        else:
            summary = str(payload)[:200]
        return emit(etype,
                    {"summary": summary, "provider": provider,
                     "kind": str(payload.get("action") or payload.get("event") or "update")},
                    source=f"webhook:{provider}")
    except Exception as e:
        return {"ok": False, "error": str(e)[:150]}
