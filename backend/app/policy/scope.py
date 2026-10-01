"""Scope evaluation — permission = tool + domain + amount + time + destination.

Answers: may this action proceed, and with what gate? Used by chat (pre-run)
and the runtime dispatcher (pre-effect). Deny-by-default on unknown tools.
"""
import time as _time

try:
    from policy.risk import classify, action_for
except ImportError:
    from app.policy.risk import classify, action_for


def evaluate(action: str, args: dict = None, ctx: dict = None) -> dict:
    """Evaluate a proposed action. Returns {decision, tier, reason}."""
    args, ctx = args or {}, ctx or {}
    text = (f"{action} " + " ".join(str(v) for v in args.values())).replace("_", " ")
    c = classify(text)
    tier = c["tier"]
    # destination sensitivity: external people/domains escalate one tier
    dest = str(args.get("to", "") or args.get("url", "") or args.get("domain", ""))
    if dest and tier in ("LOW", "MEDIUM"):
        tier = "MEDIUM" if tier == "LOW" else "HIGH"
        c["reason"] += f"; external destination {dest[:60]}"
    # quiet hours: money moves at night need explicit confirm
    try:
        hour = _time.localtime().tm_hour
    except Exception:
        hour = 12
    if c["amount"] > 0 and (hour < 6 or hour >= 23) and tier in ("MEDIUM", "HIGH"):
        tier = "CRITICAL" if tier == "HIGH" else "HIGH"
        c["reason"] += "; quiet-hours money movement"
    return {"decision": action_for(tier), "tier": tier,
            "reason": c["reason"], "amount": c["amount"]}


def gate_for_text(text: str) -> dict:
    """Chat fast-path: what gate does this message need?"""
    c = classify(text)
    return {"gate": action_for(c["tier"]), **c}
