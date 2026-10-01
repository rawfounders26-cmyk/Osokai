"""Action vocabulary — the closed registry the planner may emit.

A subtask compiles to 1+ actions from REGISTRY. Anything else is rejected at
validation time, never at runtime. Each action declares args, side effects,
and whether a human must approve. Execution mapping lands in step 3
(observe/verify/checkpoint); this module is pure contract + validation.
"""
import os

# name -> {args: {arg: type}, required: [...], effect: read|write|outside|ask,
#          approval: bool, desc}
REGISTRY = {
    "open_url": {"args": {"url": "str"}, "required": ["url"],
                 "effect": "read", "approval": False,
                 "desc": "Open a URL in Chrome via extension"},
    "web_search": {"args": {"query": "str"}, "required": ["query"],
                   "effect": "read", "approval": False,
                   "desc": "Web search, returns titles+links+snippets"},
    "fetch_page": {"args": {"url": "str"}, "required": ["url"],
                   "effect": "read", "approval": False,
                   "desc": "Fetch a page body for extraction"},
    "create_file": {"args": {"path": "str", "content": "str"}, "required": ["path", "content"],
                    "effect": "write", "approval": False,
                    "desc": "Write a file under workspace/"},
    "read_file": {"args": {"path": "str"}, "required": ["path"],
                  "effect": "read", "approval": False,
                  "desc": "Read a file under workspace/"},
    "calendar_list": {"args": {"day": "str"}, "required": [],
                      "effect": "read", "approval": False,
                      "desc": "List events for a day (YYYY-MM-DD, empty = all)"},
    "calendar_add": {"args": {"title": "str", "day": "str", "time": "str"},
                     "required": ["title"], "effect": "outside", "approval": False,
                     "desc": "Create a calendar event"},
    "email_draft": {"args": {"to": "str", "subject": "str", "body": "str"},
                    "required": ["to", "subject", "body"],
                    "effect": "outside", "approval": True,
                    "desc": "Draft email (sends only via approval outbox)"},
    "vault_fill": {"args": {"key": "str", "domain": "str"}, "required": ["key"],
                   "effect": "outside", "approval": True,
                   "desc": "Fill a credential via vault mediation (never raw secrets)"},
    "add_loop": {"args": {"title": "str", "due": "str"}, "required": ["title"],
                 "effect": "write", "approval": False,
                 "desc": "Open a tracked loop/reminder"},
    "notify_user": {"args": {"text": "str"}, "required": ["text"],
                    "effect": "ask", "approval": False,
                    "desc": "Push a notification to the user"},
    "ask_user": {"args": {"question": "str"}, "required": ["question"],
                 "effect": "ask", "approval": False,
                 "desc": "Pause for a human answer (human-kind tasks)"},
    "social_draft": {"args": {"platform": "str", "text": "str"}, "required": ["platform", "text"],
                     "effect": "write", "approval": False,
                     "desc": "Stage a social post (no side effects; publish needs approval)"},
    "social_publish": {"args": {"platform": "str", "text": "str"}, "required": ["platform", "text"],
                       "effect": "outside", "approval": True,
                       "desc": "Publish a social post (idempotent; approval-bound)"},
    "telegram_send": {"args": {"chat_id": "str", "text": "str"}, "required": ["chat_id", "text"],
                      "effect": "outside", "approval": True,
                      "desc": "Send a Telegram message (approval-bound)"},
    "whatsapp_send": {"args": {"to": "str", "text": "str"}, "required": ["to", "text"],
                      "effect": "outside", "approval": True,
                      "desc": "Send a WhatsApp message (approval-bound)"},
    "razorpay_order": {"args": {"amount": "str", "receipt": "str"}, "required": ["amount"],
                       "effect": "outside", "approval": True,
                       "desc": "Create a Razorpay order in INR (approval-bound, exact amount)"},
    "github_read": {"args": {"repo": "str", "what": "str"}, "required": ["repo"],
                    "effect": "read", "approval": False,
                    "desc": "Read GitHub issues/CI/repos (what: issues|ci|brief)"},
    "calendar_invite": {"args": {"title": "str", "day": "str", "time": "str", "attendees": "str"},
                        "required": ["title", "day"], "effect": "outside", "approval": False,
                        "desc": "Create event + draft invites (sends stay approval-gated)"},
}

_TYPES = {"str": str, "int": int, "float": (int, float), "bool": bool}


def _jail_ok(path: str) -> bool:
    try:
        from app.paths import safe_join as _sj
    except ImportError:
        from paths import safe_join as _sj
    try:
        _sj(path or "")
        return True
    except ValueError:
        return False


def validate(program) -> dict:
    """Validate a planner-emitted program. Returns {ok, errors[], needs_approval}."""
    errors = []
    needs_approval = False
    if not isinstance(program, list) or not program:
        return {"ok": False, "errors": ["program must be a non-empty list"], "needs_approval": False}
    if len(program) > 12:
        errors.append("program too long (max 12 actions)")
    for i, step in enumerate(program[:12]):
        where = f"step {i}"
        if not isinstance(step, dict):
            errors.append(f"{where}: must be an object")
            continue
        name = step.get("action", "")
        spec = REGISTRY.get(name)
        if not spec:
            errors.append(f"{where}: unknown action '{name}' — not in registry")
            continue
        args = step.get("args", {})
        if not isinstance(args, dict):
            errors.append(f"{where}: args must be an object")
            continue
        for req in spec["required"]:
            if req not in args or args[req] in ("", None):
                errors.append(f"{where}: missing required arg '{req}'")
        for k, v in args.items():
            want = spec["args"].get(k)
            if want is None:
                errors.append(f"{where}: unknown arg '{k}' for '{name}'")
            elif not isinstance(v, _TYPES[want]):
                errors.append(f"{where}: arg '{k}' must be {want}")
        for k in ("path",):
            if k in args and isinstance(args[k], str) and not _jail_ok(args[k]):
                errors.append(f"{where}: path escapes workspace jail")
        if name == "open_url" or name == "fetch_page":
            u = str(args.get("url", ""))
            if not u.startswith(("https://", "http://")):
                errors.append(f"{where}: url must be http(s)")
        if spec["approval"]:
            needs_approval = True
    return {"ok": not errors, "errors": errors, "needs_approval": needs_approval}


# keyword -> action templates for deterministic subtask compilation (step 3 executes)
_RULES = [
    (("invite", "attendees", "rsvp"), [
        {"action": "calendar_invite", "args": {"title": "", "day": "", "time": "", "attendees": ""}}]),
    (("calendar", "schedule", "meeting", "slot", "availability"), [
        {"action": "calendar_list", "args": {"day": ""}}]),
    (("telegram", "send a tg"), [
        {"action": "telegram_send", "args": {"chat_id": "", "text": ""}}]),
    (("whatsapp", "wa message"), [
        {"action": "whatsapp_send", "args": {"to": "", "text": ""}}]),
    (("email", "mail", "outreach", "send", "rsvp"), [
        {"action": "email_draft", "args": {"to": "", "subject": "", "body": ""}}]),
    (("search", "research", "find", "compare", "look up", "identify", "collect"), [
        {"action": "web_search", "args": {"query": ""}}]),
    (("open", "visit", "website", "page", "browse"), [
        {"action": "open_url", "args": {"url": ""}}]),
    (("create", "draft", "write", "build", "prepare", "slides", "deck", "file", "report"), [
        {"action": "create_file", "args": {"path": "", "content": ""}}]),
    (("remind", "track", "follow up", "deadline"), [
        {"action": "add_loop", "args": {"title": ""}}]),
    (("otp", "password", "login", "credential", "vault"), [
        {"action": "vault_fill", "args": {"key": ""}}]),
    (("post", "tweet", "share on", "publish", "announce", "linkedin"), [
        {"action": "social_draft", "args": {"platform": "", "text": ""}}]),
    (("github", "repo", "issues", "pull request", "ci "), [
        {"action": "github_read", "args": {"repo": "", "what": "brief"}}]),
    (("invite", "attendees", "rsvp"), [
        {"action": "calendar_invite", "args": {"title": "", "day": "", "time": "", "attendees": ""}}]),
]


def propose(subtask_title: str, task_kind: str = "") -> list:
    """Deterministic subtask -> candidate actions. Args left blank for the executor to fill."""
    t = (subtask_title or "").lower()
    if task_kind in ("human",):
        return [{"action": "ask_user", "args": {"question": subtask_title}}]
    if task_kind in ("approval",):
        return [{"action": "notify_user", "args": {"text": subtask_title}}]
    out = []
    for keywords, templates in _RULES:
        if any(k in t for k in keywords):
            out.extend(templates)
            if len(out) >= 3:
                break
    if not out:
        out = [{"action": "web_search", "args": {"query": subtask_title[:200]}}]
    # de-dupe by action name, keep order
    seen, dedup = set(), []
    for a in out:
        if a["action"] not in seen:
            seen.add(a["action"])
            dedup.append(a)
    return dedup[:3]
