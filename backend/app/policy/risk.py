"""Risk tiers — READ auto / LOW auto / MEDIUM notify / HIGH approval / CRITICAL confirm.

Replaces keyword-only gating with scored evaluation over action + domain +
amount + destination. Deterministic, testable, no LLM in the loop.
"""
import re

# (tier, patterns, amount_threshold_inr)
RULES = [
    ("CRITICAL", [r"\bformat\b.*\bdrive\b", r"\bdelete\b.*\baccount\b", r"\btransfer\b.*\d{5,}",
                  r"\bpay\b.*\d{5,}", r"\bpassword\b", r"\botp\b", r"\bcvv\b"], 50000),
    ("HIGH", [r"\bsend\b.*\bemail\b", r"\bdelete\b", r"\bpayment\b", r"\bbuy\b", r"\border\b",
               r"\bpay\b", r"\bpost to\b", r"\bwhatsapp send\b", r"\bsubmit\b.*\bpayment\b",
               r"\bsend\b", r"\bemail\b", r"\bcomplaint\b", r"\bleave\b",
               r"\bpost\b", r"\bpublish\b", r"\btweet\b", r"\bannounce\b",
               r"\btelegram\b", r"\bwhatsapp\b"], 10000),
    ("MEDIUM", [r"\bschedule\b", r"\bpublish\b", r"\bshare\b.*\blink\b", r"\binstall\b",
                 r"\bsettle\b", r"\bsplit\b.*\d"], 0),
]

AMOUNT_RE = re.compile(
    r"(?:rs\.?|₹|\$)\s?([\d,\.]+)|([\d,\.]+)\s?(?:rs|inr|rupees)\b|([\d\.]+)\s?(lakh|lac|l|crore|cr|k)\b", re.I)


def _amount_inr(text: str) -> float:
    m = AMOUNT_RE.search(text or "")
    if not m:
        return 0.0
    try:
        if m.group(3):
            mult = {"lakh": 1e5, "lac": 1e5, "l": 1e5, "crore": 1e7, "cr": 1e7, "k": 1e3}[m.group(4).lower()]
            return float(m.group(3)) * mult
        return float((m.group(1) or m.group(2) or "0").replace(",", ""))
    except Exception:
        return 0.0


MONEY_VERBS = r"\b(pay|buy|purchase|book|order|spend|transfer|invest|subscribe|rent out)\b"


def classify(text: str) -> dict:
    """Return {tier, reason, amount}. Pure function — cheap to eval exhaustively."""
    t = (text or "").lower()
    amount = _amount_inr(t)
    moves_money = bool(re.search(MONEY_VERBS, t))
    if amount >= 50000 and moves_money:
        return {"tier": "CRITICAL", "reason": f"spends ₹{amount:,.0f} ≥ 50000", "amount": amount}
    # a reminder ABOUT money is not moving money — notify, don't gate
    if re.search(r"\bremind", t) and re.search(r"\b(pay|payment|bill|rent)\b", t):
        return {"tier": "MEDIUM", "reason": "money reminder (not a payment)", "amount": amount}
    # initiating collection IS money movement — gate it
    if re.search(r"\bcollect\b", t) and amount > 0:
        return {"tier": "HIGH", "reason": f"initiating collection of ₹{amount:,.0f}", "amount": amount}
    for tier, patterns, threshold in RULES:
        for pat in patterns:
            if re.search(pat, t):
                if threshold and amount >= threshold:
                    return {"tier": "CRITICAL" if tier == "HIGH" else tier,
                            "reason": f"pattern + amount ₹{amount:,.0f}", "amount": amount}
                return {"tier": tier, "reason": f"matched '{pat}'", "amount": amount}
    if amount >= 10000:
        if moves_money:
            return {"tier": "HIGH", "reason": f"spends ₹{amount:,.0f} ≥ 10000", "amount": amount}
        return {"tier": "MEDIUM", "reason": f"budget mentioned ₹{amount:,.0f} (planning is free)", "amount": amount}
    if amount > 0:
        return {"tier": "MEDIUM", "reason": f"money involved ₹{amount:,.0f}", "amount": amount}
    return {"tier": "LOW", "reason": "no sensitive signals", "amount": 0.0}


def action_for(tier: str) -> str:
    return {"LOW": "auto", "MEDIUM": "notify", "HIGH": "approval", "CRITICAL": "confirm"}.get(tier, "approval")
