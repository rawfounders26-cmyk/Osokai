"""Effect-aware approval dispatcher (F19) — one gate for every external effect.

validate() says an action needs approval; this module BINDS that approval to
the exact action+arguments in a persistent record, and execute_approved() only
runs when the stored binding matches byte-for-byte. Drafting ≠ sending, and
no path can act on a mismatched or missing approval. Reuses the durable
memory approvals table (no duplicate stores).
"""
import json


def _validate(step: dict):
    try:
        from actions import validate
    except ImportError:
        from app.actions import validate
    return validate([step])


def _mem():
    # top-level first (tests + app-cwd), app.* fallback (server): one copy per env
    try:
        from memory import Memory
    except ImportError:
        from app.memory import Memory
    return Memory()


def request(action: str, args: dict = None, device: str = "dispatcher") -> dict:
    """Pre-effect gate. Returns {ok:True} (proceed) or {ok:False, waiting, approval_id}."""
    args = args or {}
    v = _validate({"action": action, "args": args})
    if not v["ok"]:
        return {"ok": False, "error": v["errors"][0] if v["errors"] else "rejected"}
    if not v["needs_approval"]:
        return {"ok": True, "auto": True}
    mem = _mem()
    binding = json.dumps({"action": action, "args": args}, sort_keys=True)
    aid = mem.approval_create(f"{action} {str(args)[:150]}", device, "action", binding)
    return {"ok": False, "waiting": True, "approval_id": aid,
            "reply": f"Approval #{aid} required for {action} — approve to execute exactly this."}


def execute_approved(approval_id: int, action: str, args: dict = None, device: str = "dispatcher") -> dict:
    """Run ONLY on a granted approval whose binding matches exactly."""
    args = args or {}
    mem = _mem()
    a = mem.approval_get(approval_id)
    if not a:
        return {"ok": False, "error": "no such approval"}
    try:
        bound = json.loads(a.get("item") or "{}")
    except Exception:
        return {"ok": False, "error": "approval binding unreadable — refusing"}
    want = json.dumps({"action": action, "args": args}, sort_keys=True)
    if json.dumps(bound, sort_keys=True) != want:
        return {"ok": False, "error": "approval binding mismatch — action/args changed after approval"}
    if a["status"] != "allowed":
        return {"ok": False, "error": "no granted approval for this execution"}
    try:
        from verify import execute as _exec
    except ImportError:
        from app.verify import execute as _exec
    out = _exec({"action": action, "args": args}, device)
    try:
        # single atomic UPDATE is self-consistent; no lock needed
        mem.db.execute("UPDATE approvals SET status='consumed', reply='consumed by dispatcher (single-use)' WHERE id=? AND status='allowed'",
                       (approval_id,))
        mem.db.commit()
    except Exception:
        pass
    return out
