"""Spend optimizer — turns the cost dashboard into a growth loop.

Reads usage history, prices each route (local = $0, slm = $0, groq = metered),
and recommends the cheapest capable route per task. `apply_policy()` is what
chat calls: deterministic today, learning tomorrow. Savings compound monthly.
"""
import os

try:
    from app.usage import PRICE_PER_1K, _db as _udb, summary as _summary
except ImportError:
    from usage import PRICE_PER_1K, _db as _udb, summary as _summary

POLICY = os.getenv("OSOKAI_ROUTE_POLICY", "auto")  # auto | groq-always | local-max


def task_costs(days: int = 30):
    """Avg $/call per task from history — the learning signal."""
    import time as _t
    since = _t.time() - days * 86400
    db = _udb()
    try:
        rows = db.execute("SELECT task, COUNT(*), SUM(tokens) FROM usage_log WHERE ts>=? GROUP BY task",
                          (since,)).fetchall()
    except Exception:
        rows = []
    out = {}
    for task, n, tok in rows:
        avg_tok = (tok or 0) / max(1, n)
        out[task] = {"calls": n, "avg_tokens": round(avg_tok),
                     "avg_cost_usd": round(avg_tok / 1000 * PRICE_PER_1K, 5)}
    return out


def recommend(task: str, confidence: float, slm_ready: bool = False) -> dict:
    """Cheapest capable route. Never downgrades a certain-local or forces groq."""
    if confidence >= 0.99:
        return {"route": "local", "reason": "certain on-device"}
    if POLICY == "groq-always":
        return {"route": "groq", "reason": "policy: groq-always"}
    if POLICY == "local-max" and confidence >= 0.5:
        return {"route": "slm" if slm_ready else "local-best-effort", "reason": "policy: local-max"}
    if slm_ready and confidence >= 0.5:
        return {"route": "slm", "reason": "SLM-zone, weights ready"}
    if confidence >= 0.5:
        return {"route": "groq", "reason": "SLM-zone but no weights — escalated (install weights to save)"}
    return {"route": "groq", "reason": "needs full model"}


def report(days: int = 30) -> dict:
    costs = task_costs(days)
    s = _summary(days)
    groq_calls = sum(v["calls"] for k, v in costs.items() if k not in ("local", "slm"))
    slm_zone_est = s.get("local_calls", 0)
    avg = (s.get("month_spent_usd", 0.0) / max(1, groq_calls)) if groq_calls else 0
    return {"by_task": costs, "month_spent_usd": s.get("month_spent_usd", 0.0),
            "local_calls": slm_zone_est, "est_saved_usd": s.get("est_saved_usd", 0.0),
            "policy": POLICY,
            "projected_monthly_savings_usd": round(slm_zone_est * 0 + groq_calls * avg * 0.4, 4),
            "note": "projection: routing 40% of groq calls to SLM once weights land"}
