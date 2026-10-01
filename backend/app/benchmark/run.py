"""Benchmark runner — PLAN (offline, CI-safe) + LIVE (opt-in, budgeted).

PLAN: for each task, capability routing must surface an expected tool and the
policy gate must match the approval expectation. No LLM, no network.
LIVE: runs a capped subset through the agent loop, recording success, steps,
cost, interventions (approvals opened), and policy blocks. History persists
so progress compounds run over run.
"""
import os
import time

try:
    from app.db import connect as _hardb
    from app.paths import data as _pdata
except ImportError:
    from db import connect as _hardb
    from paths import data as _pdata

DB = _pdata("osokai.db")


def _db():
    db = _hardb(os.path.normpath(DB))
    db.execute("""CREATE TABLE IF NOT EXISTS benchmark_runs(
        id INTEGER PRIMARY KEY, mode TEXT, total INT, passed INT, failed INT,
        cost_usd REAL DEFAULT 0, interventions INT DEFAULT 0,
        note TEXT DEFAULT '', ts REAL)""")
    return db


def _tools():
    try:
        from app.capabilities import TOOL_KEYWORDS, BASE
    except ImportError:
        from capabilities import TOOL_KEYWORDS, BASE
    return list(TOOL_KEYWORDS) + [b for b in BASE if b not in TOOL_KEYWORDS]


def run_plan(category: str = "") -> dict:
    """Offline accuracy: routing + approval flags across the battery."""
    try:
        from app.benchmark.tasks import TASKS
        from app.capabilities import route as _route
        from app.policy.scope import gate_for_text as _gate
    except ImportError:
        from benchmark.tasks import TASKS
        from capabilities import route as _route
        from policy.scope import gate_for_text as _gate
    names = _tools()
    passed, failed, by_cat = 0, [], {}
    for tid, cat, prompt, expect_tools, expect_approval in TASKS:
        if category and cat != category:
            continue
        r = _route(prompt, [], names)
        tool_ok = any(t in r["tools"] for t in expect_tools)
        gate = _gate(prompt)["gate"]
        appr_ok = (gate in ("approval", "confirm")) == expect_approval
        by_cat.setdefault(cat, {"pass": 0, "total": 0})
        by_cat[cat]["total"] += 1
        if tool_ok and appr_ok:
            passed += 1
            by_cat[cat]["pass"] += 1
        else:
            failed.append({"id": tid, "prompt": prompt,
                           "missing_tool": not tool_ok, "approval_mismatch": not appr_ok})
    total = passed + len(failed)
    _record("plan", total, passed, len(failed), 0.0, 0, f"category={category or 'all'}")
    return {"ok": True, "mode": "plan", "total": total, "passed": passed,
            "failed": failed, "by_category": by_cat,
            "score": round(100 * passed / max(1, total), 1)}


def run_live(limit: int = 5, category: str = "", max_cost_usd: float = 1.0) -> dict:
    """Capped live run. Requires GROQ key + explicit opt-in env. Never in CI."""
    import os as _os
    if _os.getenv("OSOKAI_BENCH_LIVE", "") != "1":
        return {"ok": False, "error": "live runs need OSOKAI_BENCH_LIVE=1 (never in CI)"}
    try:
        from app.benchmark.tasks import TASKS
        from app.agent import run_goal
        from app.memory import Memory
        from app.usage import summary as _sum
    except ImportError:
        from benchmark.tasks import TASKS
        from agent import run_goal
        from memory import Memory
        from usage import summary as _sum
    mem = Memory()
    picked = [t for t in TASKS if (not category or t[1] == category)][:max(1, limit)]
    results, interventions = [], 0
    for tid, cat, prompt, _, _ in picked:
        if _sum(30).get("month_spent_usd", 0.0) >= max_cost_usd:
            results.append({"id": tid, "ok": False, "note": "budget cap hit"})
            continue
        aid_before = {a["id"] for a in mem.approval_list_pending()}
        try:
            out = run_goal(f"{prompt} (benchmark {tid}: be concrete, 3 steps max)")
            ok = not str(out).startswith("[osok-ai-error]")
        except Exception as e:
            out, ok = f"error: {e}"[:300], False
        new_appr = [a for a in mem.approval_list_pending() if a["id"] not in aid_before]
        interventions += len(new_appr)
        results.append({"id": tid, "ok": ok, "interventions": len(new_appr),
                        "note": str(out)[:200]})
    spent = _sum(30).get("month_spent_usd", 0.0)
    ok_n = sum(1 for r in results if r["ok"])
    _record("live", len(results), ok_n, len(results) - ok_n, spent, interventions,
            f"category={category or 'all'}")
    return {"ok": True, "mode": "live", "total": len(results), "passed": ok_n,
            "interventions": interventions, "month_spent_usd": spent, "results": results}


def _record(mode, total, passed, failed, cost, interventions, note):
    try:
        db = _db()
        db.execute("INSERT INTO benchmark_runs(mode, total, passed, failed, cost_usd, interventions, note, ts) VALUES(?,?,?,?,?,?,?,?)",
                   (mode, total, passed, failed, cost, interventions, note[:200], time.time()))
        db.commit()
    except Exception:
        pass


def history(limit: int = 10):
    try:
        rows = _db().execute("SELECT id, mode, total, passed, failed, cost_usd, interventions, note, ts FROM benchmark_runs ORDER BY id DESC LIMIT ?",
                             (max(1, min(50, limit)),)).fetchall()
    except Exception:
        return []
    return [{"id": r[0], "mode": r[1], "total": r[2], "passed": r[3], "failed": r[4],
             "cost_usd": r[5], "interventions": r[6], "note": r[7], "ts": r[8]} for r in rows]


def interventions_per_goal(limit: int = 20) -> dict:
    """North-star input: approvals opened per goal pursuit, attributed via event
    windows (goal.created -> next goal.created). Lower is better; the trend is
    the product metric, not any single number."""
    try:
        try:
            from app.context.events import list_events
        except ImportError:
            from context.events import list_events
        goals = list_events("goal.created", limit=max(1, min(50, limit)))
        goals = sorted(goals, key=lambda e: e["ts"])
        approvals = list_events("approval.requested", limit=500)
        detail, total = [], 0
        for i, g in enumerate(goals):
            end = goals[i + 1]["ts"] if i + 1 < len(goals) else time.time()
            n = sum(1 for a in approvals if g["ts"] <= a["ts"] < end)
            total += n
            detail.append({"goal": str(g["payload"].get("title", ""))[:60], "interventions": n})
        detail.reverse()
        avg = round(total / max(1, len(detail)), 2)
        return {"goals": len(detail), "avg_interventions": avg, "detail": detail[:20]}
    except Exception:
        return {"goals": 0, "avg_interventions": 0.0, "detail": []}
