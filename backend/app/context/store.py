"""Context store — the agent's current snapshot of the user's world.

Assembled on demand (planner reads it before every plan): open goals + tasks,
pending approvals, due loops, today's calendar, recent events, month spend.
One function, no new screens, same endpoints carry it to chat when needed.
"""
import time


def snapshot() -> dict:
    out = {"ts": time.time(), "goals": [], "approvals": [],
           "loops_due": [], "today": [], "recent_events": [], "spend": {}}
    try:
        try:
            from app import goaltrees as _gt
        except ImportError:
            import goaltrees as _gt
        for g in _gt.list_trees():
            if g["progress"] < 100:
                out["goals"].append({"id": g["id"], "title": g["title"], "progress": g["progress"]})
    except Exception:
        pass
    try:
        try:
            from app.memory import Memory
        except ImportError:
            from memory import Memory
        out["approvals"] = [{"id": a["id"], "message": (a.get("message") or "")[:150]}
                            for a in Memory().approval_list_pending()]
    except Exception:
        pass
    try:
        try:
            from app.loops import due_now
        except ImportError:
            from loops import due_now
        out["loops_due"] = [{"id": l.get("id"), "title": l.get("title", "")} for l in due_now()]
    except Exception:
        pass
    try:
        try:
            from app import calendar as _cal
        except ImportError:
            import calendar as _cal
        out["today"] = [{"title": e.get("title", ""), "time": e.get("time", "")}
                        for e in _cal.list_all(_cal.today_str())]
    except Exception:
        pass
    try:
        try:
            from app.context.events import list_events
        except ImportError:
            from context.events import list_events
        out["recent_events"] = [
            {"type": e["type"], "ts": e["ts"],
             "summary": str(e["payload"].get("title") or e["payload"].get("text") or "")[:120]}
            for e in list_events(since=time.time() - 86400, limit=15)]
    except Exception:
        pass
    try:
        try:
            from app.usage import summary as _sum
        except ImportError:
            from usage import summary as _sum
        s = _sum(30)
        out["spend"] = {"month_usd": s.get("month_spent_usd", 0.0),
                        "over_budget": s.get("over_budget", False)}
    except Exception:
        pass
    return out


def brief() -> str:
    """One-paragraph world state for prompts and the morning briefing."""
    s = snapshot()
    parts = []
    if s["approvals"]:
        parts.append(f"{len(s['approvals'])} approval(s) waiting")
    if s["loops_due"]:
        parts.append(f"{len(s['loops_due'])} loop(s) due")
    if s["today"]:
        parts.append(f"today: {', '.join(e['title'] for e in s['today'][:3])}")
    open_goals = [g for g in s["goals"] if g["progress"] < 100]
    if open_goals:
        parts.append(f"open goals: {', '.join(g['title'] for g in open_goals[:3])}")
    return "; ".join(parts) or "all clear"
