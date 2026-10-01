"""Capability router — goal-aware tool selection replacing keyword flags.

Scores every tool by (a) weighted keyword overlap with the goal and (b) overlap
with the acting roles' ids + descriptions. Base capabilities always ride along;
the set is capped so function-calling stays reliable. Deterministic and
explainable: every included tool carries its reason.
"""
import re

BASE = ("open_url", "open_app", "browser", "web_search", "profile_get")

# tool -> keyword weights. Multi-word intent phrases weigh more than loose words.
TOOL_KEYWORDS = {
    "fetch_url": ["read page", "web page", "extract", "scrape", "article", "fetch", "site content"],
    "seo_check": ["seo", "rankings", "search traffic", "audit site", "meta tags"],
    "cal_add": ["schedule", "meeting", "appointment", "calendar", "remind me", "add event"],
    "cal_list": ["schedule", "calendar", "meetings today", "what's on", "agenda"],
    "email_compose": ["email", "mail", "outreach", "send", "draft", "rsvp", "invitation"],
    "trip_plan": ["trip", "road trip", "travel", "itinerary", "pondicherry", "goa", "vacation"],
    "profile_set": ["my name", "i live", "my city", "save", "upi id", "budget"],
    "pref_add": ["prefer", "like", "remember", "favorite", "favourite", "habit"],
    "shell": ["code", "script", "run", "pytest", "debug", "test", "repo", "npm", "python"],
    "git": ["git", "repo", "commit", "version control"],
    "rag_ask": ["my docs", "workspace", "ask my", "notes", "my files", "knowledge base"],
    "research": ["research", "deep dive", "competitors", "market", "compare", "analysis"],
    "build_agent": ["sub-agent", "agent for", "automate"],
    "loop_add": ["remind", "follow up", "call back", "reply to", "loop", "habit", "promise"],
    "loop_done": ["done", "finished", "closed", "complete the loop"],
    "loop_due": ["due", "overdue", "pending"],
    "bill_group": ["group", "flatmates", "roommates", "friends", "create group"],
    "bill_groups": ["groups", "list groups"],
    "bill_expense": ["split", "expense", "dinner", "bill", "paid", "share"],
    "bill_balances": ["balance", "who owes", "owes", "debts"],
    "bill_settle": ["settle", "paid back", "clear dues"],
    "wardrobe_add": ["add", "wardrobe", "shirt", "buy clothes"],
    "wardrobe_list": ["wardrobe", "clothes", "what do i own"],
    "outfit_suggest": ["wear", "outfit", "dress", "look", "occasion", "fashion"],
    "make_pptx": ["ppt", "slides", "presentation", "deck", "pitch"],
    "make_xlsx": ["excel", "spreadsheet", "sheet", "budget", "xlsx", "table"],
    "write_file": ["write", "create file", "report", "draft", "document", "notes", "code"],
    "make_dir": ["folder", "directory", "organize files"],
    "run_tests": ["pytest", "tests pass", "test the code"],
    "img_op": ["resize", "convert", "compress", "thumbnail", "meme", "image edit"],
    "img_generate": ["generate image", "create image", "wallpaper", "picture of", "logo"],
    "save_images": ["save images", "download pictures", "photos"],
    "open_url": ["open", "website", "link", "youtube", "google"],
    "open_app": ["open app", "notepad", "calculator", "spotify", "chrome"],
    "browser": ["browser", "click", "form", "login", "automate site", "web task"],
    "web_search": ["search", "find", "look up", "google"],
    "profile_get": ["who am i", "my details", "my budget", "my city"],
}

MAX_TOOLS = 18


def _words(text: str):
    return re.findall(r"[a-z]{3,}", (text or "").lower())


def route(goal: str, roles=None, available=None):
    """Return {tools: [names in registry order], reasons: {name: why}}."""
    roles = roles or []
    gw = set(_words(goal))
    role_blob = " ".join(roles).lower().replace("-", " ").replace("_", " ")
    rw = set(_words(role_blob))
    scored = {}
    for tool, kws in TOOL_KEYWORDS.items():
        pts, why = 0.0, []
        for kw in kws:
            kwl = kw.lower()
            if " " in kwl:
                if kwl in (goal or "").lower():
                    pts += 3.0
                    why.append(f"phrase '{kw}'")
                elif kwl in role_blob:
                    pts += 1.5
                    why.append(f"role phrase '{kw}'")
            else:
                gl = (goal or "").lower()
                if kwl in gw or any(kwl in w or w in kwl for w in gw):
                    pts += 1.0
                    why.append(f"word '{kw}'")
                elif any(kwl in w or w in kwl for w in rw):
                    pts += 0.75
                    why.append(f"role '{kw}'")
        if pts > 0:
            scored[tool] = (pts, why[0])
    for tool in BASE:
        if tool not in scored:
            scored[tool] = (0.01, "base capability")
    if available is not None:
        scored = {t: s for t, s in scored.items() if t in set(available)}
    ranked = sorted(scored, key=lambda t: -scored[t][0])[:MAX_TOOLS]
    # base tools first (stable order), then by score
    ranked = sorted(ranked, key=lambda t: (0 if t in BASE else 1, -scored[t][0]))
    order = list(TOOL_KEYWORDS) + [b for b in BASE if b not in TOOL_KEYWORDS]
    ranked = sorted(ranked, key=lambda t: order.index(t) if t in order else 999)
    return {"tools": ranked, "reasons": {t: scored[t][1] for t in ranked}}
