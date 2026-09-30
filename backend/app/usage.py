"""Usage + cost dashboard — every LLM call accounted for.

Token estimates (chars/4, no tokenizer dep), per-day rollups, monthly budgets
with soft caps. The orchestrator checks the budget before autonomous steps;
humans see spend in one glance. Nobody in this class shows cost — we do.
"""
import os
import sqlite3
import time

try:
    from app.paths import data as _pdata
except ImportError:
    from paths import data as _pdata

DB = _pdata("osokai.db")
# rough blended $/1k tokens for the small models Osok-AI uses (override via env)
PRICE_PER_1K = float(os.getenv("OSOKAI_PRICE_PER_1K", "0.0004"))


def _db():
    db = sqlite3.connect(os.path.normpath(DB), check_same_thread=False)
    db.execute("""CREATE TABLE IF NOT EXISTS usage_log(
        id INTEGER PRIMARY KEY, task TEXT, model TEXT, tokens INT, ms INT, ts REAL)""")
    db.execute("CREATE TABLE IF NOT EXISTS budgets(id INTEGER PRIMARY KEY CHECK(id=1), monthly_cap_usd REAL)")
    return db


def estimate_tokens(prompt: str, reply: str) -> int:
    return max(1, (len(prompt or "") + len(reply or "")) // 4)


def log(task: str, model: str, prompt: str, reply: str, ms: int = 0):
    try:
        db = _db()
        db.execute("INSERT INTO usage_log(task, model, tokens, ms, ts) VALUES(?,?,?,?,?)",
                   ((task or "")[:200], (model or "")[:80], estimate_tokens(prompt, reply), ms, time.time()))
        db.commit()
    except Exception:
        pass


def summary(days: int = 30):
    db = _db()
    since = time.time() - days * 86400
    try:
        rows = db.execute(
            "SELECT substr(date(ts,'unixepoch'),1,7) m, COUNT(*), SUM(tokens), SUM(ms) "
            "FROM usage_log WHERE ts>=? GROUP BY m ORDER BY m DESC", (since,)).fetchall()
    except Exception:
        rows = []
    months = [{"month": r[0], "calls": r[1], "tokens": r[2] or 0,
               "cost_usd": round((r[2] or 0) / 1000 * PRICE_PER_1K, 4),
               "avg_ms": round((r[3] or 0) / max(1, r[1]))} for r in rows]
    month_key = time.strftime("%Y-%m")
    spent = next((m["cost_usd"] for m in months if m["month"] == month_key), 0.0)
    cap = get_budget()
    by_task = []
    try:
        by_task = [{"task": r[0], "calls": r[1], "tokens": r[2] or 0}
                   for r in db.execute("SELECT task, COUNT(*), SUM(tokens) FROM usage_log "
                                       "WHERE ts>=? GROUP BY task ORDER BY SUM(tokens) DESC LIMIT 10", (since,))]
    except Exception:
        pass
    return {"months": months, "by_task": by_task, "month_spent_usd": spent,
            "monthly_cap_usd": cap, "over_budget": bool(cap and spent >= cap)}


def get_budget():
    try:
        r = _db().execute("SELECT monthly_cap_usd FROM budgets WHERE id=1").fetchone()
        return r[0] if r else 0.0
    except Exception:
        return 0.0


def set_budget(cap_usd: float):
    db = _db()
    db.execute("INSERT OR REPLACE INTO budgets(id, monthly_cap_usd) VALUES(1,?)", (max(0.0, cap_usd),))
    db.commit()
    return {"ok": True, "monthly_cap_usd": max(0.0, cap_usd)}


def budget_ok() -> bool:
    """Autonomy gate: orchestrator + proactive heavy work stop when over budget."""
    cap = get_budget()
    if not cap:
        return True
    return summary(31).get("month_spent_usd", 0.0) < cap
