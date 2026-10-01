"""Consolidation — nightly rollup job (scheduler kind `memory_consolidate`).

Turns → episodes: significant events from the bus become durable memories.
Decay: low-importance episodes older than 90 days are forgotten.
Prune: consumed wake firings older than 7 days go.
Returns counts; never raises.
"""
import time as _time

SIGNIFICANT = ("goal.completed", "goal.stalled", "approval.resolved",
               "task.completed", "task.failed", "bill.expense_added")


def _summarize(etype: str, payload: dict) -> str:
    title = str(payload.get("title") or payload.get("text") or payload.get("message") or "")[:150]
    mapping = {
        "goal.completed": f"Completed goal: {title}",
        "goal.stalled": f"Goal stalled: {title}",
        "approval.resolved": f"Approval {payload.get('id')}: {payload.get('status')}",
        "task.completed": "Finished a goal task" + (f": {title}" if title else ""),
        "task.failed": "A goal task failed" + (f": {payload.get('note', '')}" if payload.get("note") else ""),
        "bill.expense_added": f"Spent ₹{payload.get('amount', 0)} on {title}",
    }
    return mapping.get(etype, f"{etype}: {title}")


def run() -> dict:
    made, decayed, pruned = 0, 0, 0
    try:
        try:
            from context.events import list_events
            from memory.episodic import log_episode, forget_before
        except ImportError:
            from app.context.events import list_events
            from app.memory.episodic import log_episode, forget_before
        since = _time.time() - 86400
        seen_texts = set()
        for ev in list_events(limit=200):
            if ev["ts"] < since or ev["type"] not in SIGNIFICANT:
                continue
            text = _summarize(ev["type"], ev["payload"])
            if text in seen_texts:
                continue
            seen_texts.add(text)
            try:
                from memory import episodic as _ep
            except ImportError:
                from app.memory import episodic as _ep
            existing = _ep.recent_episodes(limit=200)
            if any(e["text"] == text for e in existing):
                continue
            log_episode(text, 2.0 if ev["type"] in ("goal.completed", "task.failed") else 1.0)
            made += 1
        decayed = forget_before(_time.time() - 90 * 86400)
        try:
            try:
                from memory.store import db
            except ImportError:
                from app.memory.store import db
            conn = db()
            cur = conn.execute("DELETE FROM wake_fired WHERE ts<?", (_time.time() - 7 * 86400,))
            conn.commit()
            pruned = cur.rowcount
        except Exception:
            pass
    except Exception:
        pass
    return {"ok": True, "episodes": made, "decayed": decayed, "pruned": pruned}
