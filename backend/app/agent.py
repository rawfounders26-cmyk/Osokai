"""Osok-AI agent loop — ANY task/goal via Groq function calling.
Fast regex intents run first (chat endpoint); everything else lands here:
model picks tools (open_url, open_app, browser, web_search) step by step."""
import json, os, re, subprocess
import httpx
from dotenv import load_dotenv
load_dotenv()

_ACLIENT = httpx.Client(timeout=90, limits=httpx.Limits(max_connections=10, max_keepalive_connections=5))

try:
    from app.system_tools import open_app, open_url, save_images
    from app.make import make_pptx, make_xlsx, write_file, run_tests, fetch_url, make_dir
    from app.skills_index import route as route_roles, role_context
except ImportError:
    from system_tools import open_app, open_url, save_images
    from make import make_pptx, make_xlsx, write_file, run_tests, fetch_url, make_dir
    from skills_index import route as route_roles, role_context

GOAL_RE = re.compile(r"^(open|go to|goto|play|search|find|book|order|send|post|download|check|show|look up|navigate|visit|start|make|create|prepare|write|build|generate|analyze|analyse|research|test|scan|design|plan|split|settle|remind)\b", re.I)

def is_goal(text: str) -> bool:
    t = text.strip()
    if GOAL_RE.match(t):
        return True
    tl = t.lower()
    return any(w in tl for w in ("owe", "owes", "balance", "split", "settle", "bill", "expense",
                                 "outfit", "wear", "wardrobe", "dress", "clothes",
                                 "remind", "reminder", "loop", "habit",
                                 "docs", "research", "agent", "rag", "code", "repo", "pytest"))

GOAL_HINTS = ("launch", "startup", "fundrais", "apartment", "flat", "house hunt",
              "vacation", "honeymoon", "wedding", "trip plan", "plan a", "weekend",
              "help me", "move to", "relocat",
              "new job", "job hunt", "career", "exam prep", "prepare for", "organize my",
              "get fit", "fitness", "60 days", "30 days", "plan my", "start a company",
              "raise ", "grow my", "100k", "100,000")


def is_big_goal(text: str) -> bool:
    """Multi-step project-like goal -> compile a goal tree. Single actions stay tasks."""
    tl = " " + text.strip().lower() + " "
    if len(text.split()) < 4:
        return False
    return any(h.lower() in tl for h in GOAL_HINTS)

TOOLS = [
    {"type": "function", "function": {"name": "open_url", "description": "Open a URL in Chrome (hosts the Osok-AI extension). Use full https URLs.",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "open_app", "description": "Open a desktop app by name (chrome, notepad, calculator, spotify).",
        "parameters": {"type": "object", "properties": {"app": {"type": "string"}}, "required": ["app"]}}},
    {"type": "function", "function": {"name": "browser", "description": "Raw Python in the persistent browser session (helpers pre-imported: new_tab(url), page_info(), js(code), click_at_xy(x,y), cdp(domain.method,...), wait_for_load(), ensure_real_tab()). First navigation is new_tab(url). E.g. 'new_tab(\"https://x\")\\nprint(page_info())'.",
        "parameters": {"type": "object", "properties": {"args": {"type": "string"}}, "required": ["args"]}}},
    {"type": "function", "function": {"name": "web_search", "description": "Search the web, returns titles+links+snippets.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "make_pptx", "description": "Build a real .pptx in workspace. slides_json: [{\"heading\":..., \"bullets\":[...]}].",
        "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "slides_json": {"type": "string"}}, "required": ["title", "slides_json"]}}},
    {"type": "function", "function": {"name": "make_xlsx", "description": "Build a real .xlsx in workspace. sheets_json: {\"Sheet1\": [[\"h1\",\"h2\"],[\"a\",\"b\"]]}.",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "sheets_json": {"type": "string"}}, "required": ["name", "sheets_json"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Write any file (code/report/plan) into workspace/. Give filename + full content.",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "content": {"type": "string"}}, "required": ["name", "content"]}}},
    {"type": "function", "function": {"name": "make_dir", "description": "Create a folder in workspace/ (same store the mobile Files screen shows).",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "run_tests", "description": "Run pytest on workspace code. Optional target filename.",
        "parameters": {"type": "object", "properties": {"target": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "fetch_url", "description": "Read a web page as text (research).",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "save_images", "description": "Search Google Images and save N pictures to Desktop/Downloads.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "count": {"type": "integer"}, "dest": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "seo_check", "description": "Run an actionable SEO audit of a URL (title/meta/h1/alt/speed + fixes).",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "cal_add", "description": "Add calendar event. day: today/tomorrow/weekday/YYYY-MM-DD, time like 5pm.",
        "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "day": {"type": "string"}, "time": {"type": "string"}}, "required": ["title"]}}},
    {"type": "function", "function": {"name": "cal_list", "description": "List events, optional day filter.",
        "parameters": {"type": "object", "properties": {"day": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "email_compose", "description": "Draft email (goes to outbox, needs approval to send).",
        "parameters": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}, "required": ["to", "subject", "body"]}}},
    {"type": "function", "function": {"name": "trip_plan", "description": "Plan India road trip: researches route/stays/food, saves itinerary file.",
        "parameters": {"type": "object", "properties": {"origin": {"type": "string"}, "dest": {"type": "string"}, "days": {"type": "integer"}}, "required": ["origin", "dest"]}}},
    {"type": "function", "function": {"name": "img_op", "description": "Edit workspace image. op: resize|convert|compress|thumb|meme. resize needs w (h optional); convert needs fmt; compress needs q; thumb needs s; meme needs top+bottom text.",
        "parameters": {"type": "object", "properties": {"op": {"type": "string"}, "file": {"type": "string"}, "w": {"type": "integer"}, "h": {"type": "integer"}, "fmt": {"type": "string"}, "q": {"type": "integer"}, "s": {"type": "integer"}, "top": {"type": "string"}, "bottom": {"type": "string"}}, "required": ["op", "file"]}}},
    {"type": "function", "function": {"name": "img_generate", "description": "Generate an AI image from text (Flux, free) into workspace/.",
        "parameters": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}}},
    {"type": "function", "function": {"name": "profile_get", "description": "Read user identity/budget (name/city/budget). Secrets never included.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "profile_set", "description": "Save identity field: name/city/upi_id/budget_default/currency.",
        "parameters": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}}, "required": ["key", "value"]}}},
    {"type": "function", "function": {"name": "pref_add", "description": "Remember a preference. domain: shopping/style/general.",
        "parameters": {"type": "object", "properties": {"domain": {"type": "string"}, "pref": {"type": "string"}}, "required": ["domain", "pref"]}}},
    {"type": "function", "function": {"name": "shell", "description": "Run an allowlisted shell command inside workspace/ (python, pytest, node, npm, git, dir).",
        "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}},
    {"type": "function", "function": {"name": "git", "description": "Safe git ops in workspace: status|diff|log|commit|init. commit needs msg.",
        "parameters": {"type": "object", "properties": {"op": {"type": "string"}, "msg": {"type": "string"}}, "required": ["op"]}}},
    {"type": "function", "function": {"name": "rag_ask", "description": "Ask over ingested workspace docs (retrieve + cite).",
        "parameters": {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]}}},
    {"type": "function", "function": {"name": "research", "description": "Deep multi-source web research into a report file.",
        "parameters": {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]}}},
    {"type": "function", "function": {"name": "build_agent", "description": "Scaffold a new runnable sub-agent (name, purpose, comma tools). Meta power.",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "purpose": {"type": "string"}, "tools": {"type": "string"}}, "required": ["name", "purpose"]}}},
    {"type": "function", "function": {"name": "loop_add", "description": "Capture an open loop (reply/call/save/promise/habit). kind + title; due as unix timestamp or 0.",
        "parameters": {"type": "object", "properties": {"kind": {"type": "string"}, "title": {"type": "string"}, "due": {"type": "number"}}, "required": ["title"]}}},
    {"type": "function", "function": {"name": "loop_done", "description": "Close an open loop by id.",
        "parameters": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}}},
    {"type": "function", "function": {"name": "loop_due", "description": "List currently due open loops.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "bill_group", "description": "Create expense group. members: [names].",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "members": {"type": "array", "items": {"type": "string"}}}, "required": ["name", "members"]}}},
    {"type": "function", "function": {"name": "bill_groups", "description": "List expense groups with ids and members.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "bill_expense", "description": "Add shared expense. splits {who: share} or {} for equal.",
        "parameters": {"type": "object", "properties": {"gid": {"type": "integer"}, "title": {"type": "string"}, "amount": {"type": "number"}, "paid_by": {"type": "string"}, "splits": {"type": "object"}}, "required": ["gid", "title", "amount", "paid_by"]}}},
    {"type": "function", "function": {"name": "bill_balances", "description": "Simplified debts for a group.",
        "parameters": {"type": "object", "properties": {"gid": {"type": "integer"}}, "required": ["gid"]}}},
    {"type": "function", "function": {"name": "bill_settle", "description": "Record a settlement payment.",
        "parameters": {"type": "object", "properties": {"gid": {"type": "integer"}, "frm": {"type": "string"}, "to": {"type": "string"}, "amount": {"type": "number"}}, "required": ["gid", "frm", "to", "amount"]}}},
    {"type": "function", "function": {"name": "wardrobe_add", "description": "Add wardrobe item. category/color/season/formality.",
        "parameters": {"type": "object", "properties": {"category": {"type": "string"}, "color": {"type": "string"}, "season": {"type": "string"}, "formality": {"type": "string"}}, "required": ["category"]}}},
    {"type": "function", "function": {"name": "wardrobe_list", "description": "List wardrobe items.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "outfit_suggest", "description": "Get candidates + weather + prefs for today's outfit. Optional formality.",
        "parameters": {"type": "object", "properties": {"formality": {"type": "string"}}}}},
]

SYS = ("You are Osok-AI, an agent that ACTS. Routing rules (strict): "
    "SIMPLE one-shot views (open a site/video/song/episode for the user to watch) -> open_url (system Chrome, extension completes playback). "
    "COMPLEX work (research, files, plans, multi-step browser flows, logins, forms, scraping) -> SAME VM: use browser/fetch_url/write_file/make_* tools, save everything in workspace/. "
    "Never use open_url for complex work output; never save simple views as files. "
    "BUY JOURNEY: search/compare first (web_search, fetch_url, optional compare file), then STOP — payment needs human approval, never auto-pay. "
    "After approval, point at the shop URL and tell them to use extension Autofill. "
    "Use tools to complete the goal, then confirm in one line. Never say you cannot control the device.")

def _browser(args: str) -> str:
    try:
        r = subprocess.run("browser-use", shell=True, input=args, capture_output=True, text=True, timeout=120)
        out = (r.stdout or "") + ("\nERR:" + r.stderr if r.stderr else "")
        return out[:4000] or "(no output)"
    except subprocess.TimeoutExpired:
        return "(browser command timed out)"
    except Exception as e:
        return f"(browser error: {e})"

def _web_search(query: str) -> str:
    try:
        r = httpx.post("https://html.duckduckgo.com/html/", data={"q": query},
                       headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        links = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r.text)
        snips = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', r.text)
        out = []
        for i, (u, t) in enumerate(links[:8]):
            t = re.sub(r"<[^>]+>", "", t)
            s = re.sub(r"<[^>]+>", "", snips[i]) if i < len(snips) else ""
            out.append(f"{i+1}. {t} — {u}\n   {s}")
        return "\n".join(out) or "(no results)"
    except Exception as e:
        return f"(search error: {e})"

def _seo_check(url: str) -> str:
    """Actionable SEO audit: title, meta, h1s, speed basics. Powers the seo-audit skill."""
    import time
    import httpx
    if not url.startswith("http"):
        url = "https://" + url
    try:
        t0 = time.time()
        r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25, follow_redirects=True)
        secs = round(time.time() - t0, 2)
        html = r.text
        def one(pat):
            m = re.search(pat, html, re.S | re.I)
            return (m.group(1).strip()[:160] if m else "")
        title = one(r"<title[^>]*>(.*?)</title>")
        desc = one(r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']')
        h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)[:5]
        h1s = [re.sub(r"<[^>]+>", "", h).strip()[:100] for h in h1s]
        imgs_noalt = len(re.findall(r"<img(?![^>]*alt=)[^>]*>", html, re.I))
        links = len(re.findall(r"<a[^>]+href=", html, re.I))
        out = [f"URL: {url} ({r.status_code}, {secs}s, {len(html)//1024}KB)",
               f"title [{len(title)}ch]: {title or 'MISSING'}",
               f"meta description [{len(desc)}ch]: {desc or 'MISSING'}",
               f"h1 x{len(h1s)}: {' | '.join(h1s) or 'NONE'}",
               f"images missing alt: {imgs_noalt}", f"links: {links}"]
        if not title:
            out.append("FIX: add <title>")
        if len(title) > 60:
            out.append("FIX: shorten title < 60ch")
        if not desc:
            out.append("FIX: add meta description 120-160ch")
        if not h1s:
            out.append("FIX: add exactly one h1")
        if imgs_noalt:
            out.append(f"FIX: add alt to {imgs_noalt} images")
        if secs > 3:
            out.append(f"FIX: TTFB+body {secs}s — compress/cdn")
        return "\n".join(out)
    except Exception as e:
        return f"(seo error: {e})"

def _run_tool(name: str, args: dict) -> str:
    if name == "open_url":
        r = open_url(args.get("url", ""))
        return json.dumps(r)
    if name == "open_app":
        r = open_app(args.get("app", ""))
        return json.dumps(r)
    if name == "browser":
        return _browser(args.get("args", ""))
    if name == "web_search":
        return _web_search(args.get("query", ""))
    if name == "make_pptx":
        try:
            return make_pptx(args.get("title", "osokai-deck"), args.get("slides_json", "[]"))
        except Exception as e:
            return f"(pptx error: {e})"
    if name == "make_xlsx":
        try:
            return make_xlsx(args.get("name", "osokai-sheet"), args.get("sheets_json", "{}"))
        except Exception as e:
            return f"(xlsx error: {e})"
    if name == "write_file":
        try:
            return write_file(args.get("name", "osokai.txt"), args.get("content", ""))
        except Exception as e:
            return f"(write error: {e})"
    if name == "make_dir":
        try:
            return make_dir(args.get("name", "osokai-folder"))
        except Exception as e:
            return f"(mkdir error: {e})"
    if name == "run_tests":
        return run_tests(args.get("target", ""))
    if name == "fetch_url":
        return fetch_url(args.get("url", ""))
    if name == "save_images":
        try:
            return save_images(args.get("query", ""), int(args.get("count", 1)), args.get("dest", "desktop"))
        except Exception as e:
            return f"(save_images error: {e})"
    if name == "seo_check":
        return _seo_check(args.get("url", ""))
    if name in ("cal_add", "cal_list", "email_compose", "trip_plan"):
        try:
            from app import calendar as _cal, emailbox as _em, trip as _tr
        except ImportError:
            import sys as _s, os as _o
            _s.path.insert(0, _o.path.dirname(__file__))
            import calendar as _cal
            import emailbox as _em
            import trip as _tr
        try:
            if name == "cal_add":
                return _cal.add(args.get("title", ""), args.get("day", "today"), args.get("time", ""))
            if name == "cal_list":
                return _cal.list_all(args.get("day", ""))
            if name == "email_compose":
                return _em.compose(args.get("to", ""), args.get("subject", ""), args.get("body", ""))
            return _tr.plan_trip(args.get("origin", ""), args.get("dest", ""), int(args.get("days", 3)))
        except Exception as e:
            return f"(assistant error: {e})"
    if name in ("shell", "git"):
        try:
            from app import dev as _dev
        except ImportError:
            import dev as _dev
        try:
            if name == "shell":
                return _dev.shell(args.get("cmd", ""))
            return _dev.git(args.get("op", "status"), args.get("msg", ""))
        except Exception as e:
            return f"(dev error: {e})"
    if name in ("rag_ask", "research", "build_agent", "img_generate"):
        try:
            from app.rag import search as _rsearch
            from app.research import deep_research as _dr, build_agent as _ba
            from app.grok_client import chat_with_grok as _chat
            from app.img import img_generate as _gen
        except ImportError:
            from rag import search as _rsearch
            from research import deep_research as _dr, build_agent as _ba
            from grok_client import chat_with_grok as _chat
            from img import img_generate as _gen
        try:
            if name == "img_generate":
                r = _gen(args.get("prompt", ""))
                return r if isinstance(r, str) else __import__("json").dumps(r)
            if name == "rag_ask":
                hits = _rsearch(args.get("q", ""), 5)
                if not hits:
                    return "(no workspace matches — ingest docs first)"
                ctx = "\n\n".join(f"[{h['path']}] {h['snippet']}" for h in hits)
                return _chat(f"Answer from workspace excerpts (cite [path]). Q: {args.get('q','')}\n\n{ctx[:4000]}")
            if name == "research":
                return _dr(args.get("topic", ""), 3)
            return _ba(args.get("name", "agent"), args.get("purpose", ""), args.get("tools", ""))
        except Exception as e:
            return f"(knowledge error: {e})"
    if name == "img_op":
        try:
            from app import img as _img
        except ImportError:
            import img as _img
        try:
            op, f = args.get("op", ""), args.get("file", "")
            if op == "resize":
                return _img.img_resize(f, int(args.get("w", 800)), int(args.get("h", 0)))
            if op == "convert":
                return _img.img_convert(f, args.get("fmt", "png"))
            if op == "compress":
                return _img.img_compress(f, int(args.get("q", 60)))
            if op == "thumb":
                return _img.img_thumbnail(f, int(args.get("s", 256)))
            if op == "meme":
                return _img.img_caption(f, args.get("top", ""), args.get("bottom", ""))
            return "(unknown img op)"
        except Exception as e:
            return f"(img error: {e})"
    if name in ("bill_group", "bill_groups", "bill_expense", "bill_balances", "bill_settle"):
        try:
            from app import bills as _b
        except ImportError:
            import bills as _b
        try:
            if name == "bill_groups":
                return _b.list_groups()
            if name == "bill_group":
                return _b.create_group(args.get("name", "group"), args.get("members", []))
            if name == "bill_expense":
                return _b.add_expense(int(args.get("gid", 0)), args.get("title", ""), float(args.get("amount", 0)), args.get("paid_by", ""), args.get("splits") or {})
            if name == "bill_balances":
                return _b.balances(int(args.get("gid", 0)))
            return _b.settle(int(args.get("gid", 0)), args.get("frm", ""), args.get("to", ""), float(args.get("amount", 0)))
        except Exception as e:
            return f"(bills error: {e})"
    if name in ("profile_get", "profile_set", "pref_add"):
        try:
            from app import profile as _pr
        except ImportError:
            import profile as _pr
        try:
            if name == "profile_get":
                return {"profile": _pr.get_profile(), "prefs": _pr.get_prefs()}
            if name == "profile_set":
                return _pr.set_profile(args.get("key", ""), args.get("value", ""))
            return _pr.add_pref(args.get("domain", "general"), args.get("pref", ""))
        except Exception as e:
            return f"(profile error: {e})"
    if name in ("wardrobe_add", "wardrobe_list", "outfit_suggest"):
        try:
            from app import wardrobe as _w
        except ImportError:
            import wardrobe as _w
        try:
            if name == "wardrobe_add":
                return _w.add_item(args.get("category", ""), args.get("color", ""),
                                   args.get("season", "all"), args.get("formality", "casual"))
            if name == "wardrobe_list":
                return _w.list_items()
            return _w.suggest(formality=args.get("formality", ""))
        except Exception as e:
            return f"(wardrobe error: {e})"
    if name in ("loop_add", "loop_done", "loop_due"):
        try:
            from app import loops as _l
        except ImportError:
            import loops as _l
        try:
            if name == "loop_add":
                return _l.add(args.get("kind", "promise"), args.get("title", ""), "agent", float(args.get("due", 0) or 0))
            if name == "loop_done":
                return _l.close(int(args.get("id", 0)))
            return _l.due_now()
        except Exception as e:
            return f"(loops error: {e})"
    return "(unknown tool)"

def _salvage_tool_call(text: str):
    """Model sometimes writes the call as JSON text. Parse + run builder tools."""
    m = re.search(r"\{\s*\"(make_pptx|make_xlsx|write_file|open_url|open_app|web_search|fetch_url|browser)\"\s*:", text)
    if not m:
        return None
    name = m.group(1)
    start = m.start()
    depth, end = 0, None
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        return None
    try:
        args = json.loads(text[start:end])[name]
        if not isinstance(args, dict):
            return None
        return f"{name} -> {_run_tool(name, args)}"
    except Exception:
        return None

def run_goal(goal: str, max_steps: int = 8) -> str:
    key = os.getenv("GROQ_API_KEY", "") or os.getenv("GROK_API_KEY", "")
    model = os.getenv("GROK_MODEL", "qwen/qwen3-32b")
    url = "https://api.groq.com/openai/v1/chat/completions" if key.startswith("gsk_") else "https://api.x.ai/v1/chat/completions"
    roles = route_roles(goal)
    sys = SYS + (f"\nActing roles for this task: {', '.join(roles)}.\n{role_context(roles)}" if roles else "")
    try:
        from app.profile import context_block as _ctx
    except ImportError:
        try:
            from profile import context_block as _ctx
        except ImportError:
            _ctx = lambda: ""
    _uctx = _ctx()
    if _uctx:
        sys += f"\nUser context (identity+budgets+prefs; secrets are NEVER here):\n{_uctx}"
    # capability router: goal+roles aware tool selection (replaces keyword flags)
    try:
        from app.capabilities import route as _route_tools
    except ImportError:
        try:
            from capabilities import route as _route_tools
        except ImportError:
            _route_tools = None
    _all_names = [t["function"]["name"] for t in TOOLS]
    if _route_tools:
        try:
            _r = _route_tools(goal, roles, _all_names)
            tools = [t for t in TOOLS if t["function"]["name"] in set(_r["tools"])]
        except Exception:
            tools = [t for t in TOOLS if t["function"]["name"] in ("open_url", "open_app", "browser", "web_search", "fetch_url", "seo_check", "cal_add", "cal_list", "email_compose", "trip_plan", "profile_get", "profile_set", "pref_add")]
    else:
        tools = [t for t in TOOLS if t["function"]["name"] in ("open_url", "open_app", "browser", "web_search", "fetch_url", "seo_check", "cal_add", "cal_list", "email_compose", "trip_plan", "profile_get", "profile_set", "pref_add")]

    msgs = [{"role": "system", "content": sys}, {"role": "user", "content": goal}]
    body = {"model": model, "messages": msgs, "tools": tools, "max_tokens": 1500}
    def _slim():
        # older tool outputs bloat input tokens: keep latest full, trim the rest
        seen = 0
        for m in reversed(msgs):
            if m.get("role") == "tool":
                seen += 1
                if seen > 1 and isinstance(m.get("content"), str) and len(m["content"]) > 800:
                    m["content"] = m["content"][:800] + "…(trimmed)"
    try:
        for step in range(max_steps):
            # first step MUST act (required), later steps decide freely — kills describe-instead-of-do
            body["tool_choice"] = "required" if step == 0 else "auto"
            _slim()
            body["messages"] = msgs
            r = _ACLIENT.post(url, headers={"Authorization": f"Bearer {key}"}, json=body)
            for _retry in range(3):
                if r.status_code != 429:
                    break
                import time as _t
                _t.sleep(20)
                _slim()
                body["messages"] = msgs
                r = _ACLIENT.post(url, headers={"Authorization": f"Bearer {key}"}, json=body)
            try:
                r.raise_for_status()
            except Exception:
                return f"[osok-ai-error] agent loop failed: {r.status_code} {r.text[:300]}"
            msg = r.json()["choices"][0]["message"]
            calls = msg.get("tool_calls") or []
            if not calls:
                content = msg.get("content") or "done."
                salv = _salvage_tool_call(content)
                if salv:
                    mem_note = salv
                    return f"Done. {mem_note} (in workspace/ — see Files tab)"
                return content
            msgs.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": [
                {"id": c["id"], "type": "function", "function": {"name": c["function"]["name"], "arguments": c["function"].get("arguments") or "{}"}} for c in calls]})
            for c in calls:
                fn = c["function"]["name"]
                try:
                    a = json.loads(c["function"].get("arguments") or "{}")
                except Exception:
                    a = {}
                res = _run_tool(fn, a)
                if not isinstance(res, str):
                    res = json.dumps(res)
                msgs.append({"role": "tool", "tool_call_id": c["id"], "content": res})
        return "Ran out of steps — partial progress above."
    except Exception as e:
        return f"[osok-ai-error] agent loop failed: {e}"
