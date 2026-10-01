"""Normalizers — outside world in, events out. Best-effort, idempotent, silent."""
import time


def _emit(etype: str, payload: dict, source: str = ""):
    try:
        try:
            from app.context.events import emit
        except ImportError:
            from context.events import emit
        return emit(etype, payload, source)
    except Exception:
        return {"ok": False}


def goal_created(gid: int, title: str, source: str = ""):
    return _emit("goal.created", {"id": gid, "title": title, "source": source}, "goals")


def approval_requested(aid: int, message: str):
    return _emit("approval.requested", {"id": aid, "message": message[:200]}, "approvals")


def approval_resolved(aid: int, status: str):
    return _emit("approval.resolved", {"id": aid, "status": status}, "approvals")


def loop_opened(lid: int, title: str):
    return _emit("loop.opened", {"id": lid, "title": title}, "loops")


def loop_closed(lid: int):
    return _emit("loop.closed", {"id": lid}, "loops")


def calendar_created(eid: int, title: str, day: str):
    return _emit("calendar.event.created", {"id": eid, "title": title, "day": day}, "calendar")


def expense_added(eid: int, title: str, amount: float):
    return _emit("bill.expense_added", {"id": eid, "title": title, "amount": amount}, "bills")


def task_done(tid: int, title: str = ""):
    return _emit("task.completed", {"id": tid, "title": title}, "goals")


def task_failed(tid: int, note: str = ""):
    return _emit("task.failed", {"id": tid, "note": note[:200]}, "goals")


def goal_stalled(gid: int, title: str):
    return _emit("goal.stalled", {"id": gid, "title": title}, "goals")


def sync_inbox() -> int:
    """Connector unread counts -> email.received (deduped 24h per sender)."""
    try:
        try:
            from app.connectors import notifications
            from app.context.events import latest
        except ImportError:
            from connectors import notifications
            from context.events import latest
        n = notifications()
        if not n.get("unread") or not n.get("from"):
            return 0
        last = latest("email.received")
        if last and last["payload"].get("from") == n["from"] and time.time() - last["ts"] < 86400:
            return 0
        r = _emit("email.received", {"from": n["from"], "unread": n["unread"]}, "connectors")
        return 1 if r.get("ok") else 0
    except Exception:
        return 0
