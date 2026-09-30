"""Osok-AI backend — FastAPI gateway. All frontends talk here + stay in sync via /ws/sync."""
import os, time
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Header, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()
try:
    from app.grok_client import chat_with_grok
    from app.memory import Memory
    from app.sentinel import needs_approval
    from app.connectors import list_connectors, inbox_summary, auth_url, connect, disconnect, notifications, simulate, set_enabled, refresh
    from app.intents import parse as intent_parse, execute as intent_run
    from app.agent import run_goal as agent_run, is_goal as is_goal_text
except ImportError:
    from grok_client import chat_with_grok
    from memory import Memory
    from sentinel import needs_approval
    from connectors import list_connectors, inbox_summary, auth_url, connect, disconnect, notifications, simulate, set_enabled, refresh
    from intents import parse as intent_parse, execute as intent_run
    from agent import run_goal as agent_run, is_goal as is_goal_text

app = FastAPI(title="Osok-AI API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
mem = Memory()

class ChatIn(BaseModel):
    message: str
    mode: str = "general"
    device: str = "unknown"

# ---- real-time sync hub: every mutation bumps rev and pushes to all surfaces ----
class Hub:
    def __init__(self):
        self.conns = set()
        self.rev = 0
    async def add(self, ws: WebSocket):
        await ws.accept()
        self.conns.add(ws)
        await ws.send_json(state())
    def drop(self, ws: WebSocket):
        self.conns.discard(ws)
    async def push(self):
        self.rev += 1
        dead = []
        for ws in list(self.conns):
            try:
                await ws.send_json(state())
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.conns.discard(ws)

hub = Hub()
_fails = {}

def state():
    return {"rev": hub.rev,
            "connectors": list_connectors(),
            "notes": notifications(),
            "pending": mem.approval_list_pending()}

def need_auth(request: Request, authorization: str = Header(default="")):
    """Global Osok-AI token + brute-force lockout (5 fails -> 5 min per IP)."""
    want = os.getenv("OSOKAI_AUTH_TOKEN", "")
    if not want:
        return  # no token configured -> open (dev)
    ip = "?"
    try:
        if request.client:
            ip = request.client.host
    except Exception:
        pass
    now = time.time()
    rec = _fails.get(ip, {"n": 0, "until": 0})
    if rec["until"] > now:
        raise HTTPException(status_code=429, detail=f"locked — retry in {int(rec['until'] - now)}s")
    if authorization != f"Bearer {want}":
        if authorization:
            # wrong token: possible brute force -> count it. Empty header: unconfigured client -> 401 only.
            rec["n"] += 1
            if rec["n"] >= 5:
                rec.update({"n": 0, "until": now + 300})
            _fails[ip] = rec
        raise HTTPException(status_code=401, detail="bad Osok-AI token — paste it in Settings")
    _fails.pop(ip, None)

@app.get("/health")
def health():
    return {"ok": True, "service": "Osok-AI", "supabase": bool(os.getenv("SUPABASE_URL", "").startswith("http")),
            "auth": bool(os.getenv("OSOKAI_AUTH_TOKEN", ""))}

@app.post("/system/open")
async def system_open(payload: dict, _=Depends(need_auth)):
    """Direct device control: {app: 'chrome'} or {url: '...'}."""
    try:
        from app.system_tools import open_app, open_url
    except ImportError:
        from system_tools import open_app, open_url
    if payload.get("url"):
        r = open_url(payload["url"])
    else:
        r = open_app(payload.get("app", "chrome"))
    await hub.push()
    return r

@app.get("/roles")
def roles(_=Depends(need_auth)):
    try:
        from app.skills_index import list_roles
    except ImportError:
        from skills_index import list_roles
    return {"roles": list_roles()}

@app.post("/vault/set")
def vault_set(payload: dict, _=Depends(need_auth)):
    """Store card (number/expiry/cvv) or login. Encrypted at rest, masked in replies."""
    try:
        from app.vault import secret_set
    except ImportError:
        from vault import secret_set
    return secret_set(payload.get("scope", "general"), payload.get("key", ""), payload.get("value", ""))

@app.get("/vault/list")
def vault_list(_=Depends(need_auth)):
    try:
        from app.vault import secret_list
    except ImportError:
        from vault import secret_list
    return {"secrets": secret_list()}

@app.post("/vault/fill")
def vault_fill(payload: dict, _=Depends(need_auth)):
    """Decrypt ONE value for platform field entry. Enforces policy/lock/domain + audits."""
    try:
        from app.vault import secret_fill
    except ImportError:
        from vault import secret_fill
    try:
        return {"ok": True, "key": payload.get("key", ""),
                "value": secret_fill(payload.get("key", ""), payload.get("domain", ""),
                                     payload.get("device", "?"))}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@app.post("/vault/policy")
def vault_policy(payload: dict, _=Depends(need_auth)):
    try:
        from app.vault import secret_policy
    except ImportError:
        from vault import secret_policy
    try:
        return secret_policy(payload.get("key", ""), payload.get("policy", ""), payload.get("domains"))
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/vault/lock")
def vault_lock(_=Depends(need_auth)):
    try:
        from app.vault import lock
    except ImportError:
        from vault import lock
    return lock()

@app.post("/vault/unlock")
def vault_unlock(payload: dict, _=Depends(need_auth)):
    try:
        from app.vault import unlock
    except ImportError:
        from vault import unlock
    return unlock(int(payload.get("minutes", 15)))

@app.get("/vault/status")
def vault_status(_=Depends(need_auth)):
    try:
        from app.vault import lock_status
    except ImportError:
        from vault import lock_status
    return lock_status()

@app.get("/vault/audit")
def vault_audit(limit: int = 50, _=Depends(need_auth)):
    try:
        from app.vault import audit_list
    except ImportError:
        from vault import audit_list
    return {"audit": audit_list(min(limit, 200))}

@app.post("/vault/totp")
def vault_totp(payload: dict, _=Depends(need_auth)):
    """Current 30s TOTP code for a stored seed. Enforces policy/lock like fill."""
    try:
        from app.vault import secret_fill, totp_now
    except ImportError:
        from vault import secret_fill, totp_now
    key = payload.get("key", "")
    try:
        secret_fill(key, payload.get("domain", ""), payload.get("device", "?") + ":totp-check")
    except (KeyError, PermissionError) as e:
        raise HTTPException(status_code=403 if isinstance(e, PermissionError) else 404, detail=str(e))
    try:
        return {"ok": True, "key": key, "code": totp_now(key)}
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"not a TOTP seed: {e}")

@app.post("/vault/dpapi-wrap")
def vault_dpapi(_=Depends(need_auth)):
    try:
        from app.vault import dpapi_wrap_key
    except ImportError:
        from vault import dpapi_wrap_key
    return dpapi_wrap_key()

@app.post("/vault/passkey")
def vault_passkey(payload: dict, _=Depends(need_auth)):
    """Register a passkey credential ID for a site (private key stays in platform TPM).
    Extension mediates navigator.credentials.get on that device."""
    try:
        from app.vault import secret_set
    except ImportError:
        from vault import secret_set
    rp = payload.get("rp", "")
    cid = payload.get("credential_id", "")
    if not rp or not cid:
        raise HTTPException(status_code=400, detail="rp + credential_id required")
    return secret_set("passkey", f"passkey:{rp}", cid)

@app.delete("/vault/{key}")
def vault_delete(key: str, _=Depends(need_auth)):
    try:
        from app.vault import secret_delete
    except ImportError:
        from vault import secret_delete
    return secret_delete(key)

@app.get("/auth-check")
def auth_check(_=Depends(need_auth)):
    return {"ok": True, "live": True}

@app.post("/auth/rotate")
async def auth_rotate(_=Depends(need_auth)):
    """New token now, old one dead. Rewrites .env — re-paste on all surfaces."""
    import secrets as _s
    new = "OSOKAI_" + _s.token_urlsafe(24)
    envp = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    try:
        txt = open(envp).read()
        if "OSOKAI_AUTH_TOKEN=" in txt:
            txt = "\n".join(f"OSOKAI_AUTH_TOKEN={new}" if l.startswith("OSOKAI_AUTH_TOKEN=") else l for l in txt.splitlines())
        else:
            txt += f"\nOSOKAI_AUTH_TOKEN={new}\n"
        open(envp, "w").write(txt + ("" if txt.endswith("\n") else "\n"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"rotate failed: {e}")
    os.environ["OSOKAI_AUTH_TOKEN"] = new
    await hub.push()
    return {"ok": True, "token": new}

@app.post("/chat")
async def chat(body: ChatIn, _=Depends(need_auth)):
    # loops capture first: "remind me to pay X" is a reminder, not a payment
    _pre, _ = intent_parse(body.message)
    if _pre and _pre.get("type") in ("loop_add", "loop_done"):
        mem.add("user", body.message)
        reply = intent_run(_pre, body.device)
        mem.add("Osok-AI", reply)
        await hub.push()
        return {"reply": reply, "approval_required": False, "action": _pre["type"]}
    # email compose goes to outbox + approval (never sent silently)
    try:
        from app.emailbox import parse_compose, compose as _compose
    except ImportError:
        from emailbox import parse_compose, compose as _compose
    ec = parse_compose(body.message)
    if ec:
        to, subj, txt = ec
        em = _compose(to, subj, txt)
        aid = mem.approval_create(f"email to {to}: {subj}", body.device, "email", str(em["id"]))
        await hub.push()
        return {"reply": f"Email to {to} drafted (#{em['id']}). Approve #{aid} to send.",
                "approval_required": True, "approval_id": aid, "kind": "email"}
    # calendar NL: add / list / cancel
    try:
        from app import calendar as _cal
    except ImportError:
        import sys as _s, os as _o
        _s.path.insert(0, _o.path.join(_o.path.dirname(__file__)))
        import calendar as _cal
    import re as _re
    ca = _cal.parse_add(body.message)
    if ca:
        title, day, tm = ca
        r = _cal.add(title, day, tm)
        mem.add("user", body.message)
        mem.add("Osok-AI", f"Added: {title} — {r['when']}")
        await hub.push()
        return {"reply": f"Added: {title} — {r['when']}.", "approval_required": False, "action": "calendar"}
    m = _re.match(r"^(what'?s on|what is on|list|show|any)\s+(today|tomorrow|.*)?$", body.message.strip(), _re.I)
    if m and any(w in body.message.lower() for w in ("today", "tomorrow", "meeting", "schedule", "calendar", "on ")):
        day = ""
        tl = body.message.lower()
        if "tomorrow" in tl:
            import datetime as _dt
            day = (_dt.date.today() + _dt.timedelta(days=1)).isoformat()
        elif "today" in tl:
            day = _cal.today_str()
        evs = _cal.list_all(day)
        if not evs:
            return {"reply": "Nothing scheduled" + (f" for {day}" if day else "") + ".", "approval_required": False, "action": "calendar"}
        return {"reply": "\n".join(f"• {e['title']} — {e['day']} {e['time']}".strip() for e in evs),
                "approval_required": False, "action": "calendar"}
    if needs_approval(body.message):
        try:
            from app.intents import payment_parse
        except ImportError:
            from intents import payment_parse
        pay = payment_parse(body.message) or {}
        aid = mem.approval_create(body.message, body.device, pay.get("kind", "general"), pay.get("item", ""))
        await hub.push()
        what = f" for “{pay['item']}”" if pay.get("item") else ""
        return {"reply": f"Payment approval (#{aid}){what} — Approve/Reject on the extension popup or mobile chat.",
                "approval_required": True, "approval_id": aid, "kind": pay.get("kind", "general")}
    # fast-path: device/web intents execute instantly, no LLM roundtrip
    action, _ = intent_parse(body.message)
    if action:
        mem.add("user", body.message)
        reply = intent_run(action, body.device)
        mem.add("Osok-AI", reply)
        await hub.push()
        out = {"reply": reply, "approval_required": False, "action": action["type"]}
        if action["type"] in ("youtube_play", "shop_browse", "open_url"):
            out["url"] = action.get("url", "")  # mobile opens directly / links it
        return out
    # general agent: any other goal goes through the tool loop (browser/apps/search)
    if is_goal_text(body.message):
        import asyncio
        try:
            from app import tasks as _runs
        except ImportError:
            import tasks as _runs
        mem.add("user", body.message)
        rid = _runs.create(body.message[:120])
        _runs.log_step(rid, f"started on {body.device}", 5)
        try:
            reply = await asyncio.to_thread(agent_run, body.message)
            _runs.log_step(rid, "tools finished", 90)
            _runs.complete(rid, reply)
        except Exception as e:
            reply = f"[osok-ai-error] {e}"
            _runs.complete(rid, reply, "failed")
        mem.add("Osok-AI", reply)
        await hub.push()
        return {"reply": reply, "approval_required": False, "action": "agent", "run_id": rid}
    mem.add("user", body.message)
    reply = chat_with_grok(body.message)
    mem.add("Osok-AI", reply)
    await hub.push()
    return {"reply": reply, "approval_required": False}

@app.get("/approvals")
def approvals_list(_=Depends(need_auth)):
    return {"pending": mem.approval_list_pending()}

@app.post("/approvals/{aid}/resolve")
async def approvals_resolve(aid: int, payload: dict, _=Depends(need_auth)):
    a = mem.approval_get(aid)
    if not a or a["status"] != "pending":
        raise HTTPException(status_code=404, detail="approval not found")
    allow = bool(payload.get("allow"))
    if allow and a.get("kind") == "email":
        try:
            from app.emailbox import approve as _em_approve
        except ImportError:
            from emailbox import approve as _em_approve
        try:
            er = _em_approve(int(a.get("item") or 0))
            reply = f"Email {er.get('status')}: {er.get('detail', '')}"
        except Exception as e:
            reply = f"email failed: {e}"
        mem.add("user", a["message"])
        mem.add("Osok-AI", reply)
    elif allow:
        mem.add("user", a["message"])
        reply = chat_with_grok(a["message"])
        mem.add("Osok-AI", reply)
    else:
        reply = "denied by user"
    a = mem.approval_resolve(aid, allow, reply)
    await hub.push()
    return {"ok": True, **a}

@app.get("/tasks")
def tasks(_=Depends(need_auth)):
    try:
        from app import tasks as _runs
    except ImportError:
        import tasks as _runs
    return {"running": _runs.running(), "previous": mem.tasks_previous(), "runs": _runs.list_runs()}

@app.get("/tasks/runs")
def runs_list(_=Depends(need_auth)):
    try:
        from app import tasks as _runs
    except ImportError:
        import tasks as _runs
    return {"runs": _runs.list_runs(50)}

@app.get("/tasks/runs/{rid}")
def run_get(rid: int, _=Depends(need_auth)):
    try:
        from app import tasks as _runs
    except ImportError:
        import tasks as _runs
    r = _runs.get(rid)
    if not r:
        raise HTTPException(status_code=404, detail="run not found")
    return r

@app.post("/tasks/runs/{rid}/retry")
async def run_retry(rid: int, _=Depends(need_auth)):
    try:
        from app import tasks as _runs
    except ImportError:
        import tasks as _runs
    r = _runs.retry(rid)
    if not r:
        raise HTTPException(status_code=404, detail="run not found")
    await hub.push()
    return r

@app.get("/briefing")
def briefing(_=Depends(need_auth)):
    try:
        from app.briefing import build
    except ImportError:
        from briefing import build
    return build()

# ---- calendar ----
@app.post("/calendar")
async def cal_add(payload: dict, _=Depends(need_auth)):
    try:
        from app import calendar as _cal
    except ImportError:
        import sys as _s, os as _o
        _s.path.insert(0, _o.path.dirname(__file__))
        import calendar as _cal
    r = _cal.add(payload.get("title", ""), payload.get("day", "today"),
                 payload.get("time", ""), payload.get("note", ""))
    await hub.push()
    return r

@app.get("/calendar")
def cal_list(day: str = "", _=Depends(need_auth)):
    try:
        from app import calendar as _cal
    except ImportError:
        import sys as _s, os as _o
        _s.path.insert(0, _o.path.dirname(__file__))
        import calendar as _cal
    return {"events": _cal.list_all(day)}

@app.post("/calendar/cancel")
async def cal_cancel(payload: dict, _=Depends(need_auth)):
    try:
        from app import calendar as _cal
    except ImportError:
        import sys as _s, os as _o
        _s.path.insert(0, _o.path.dirname(__file__))
        import calendar as _cal
    r = _cal.cancel(payload.get("id") or payload.get("title", ""))
    await hub.push()
    return r

@app.get("/calendar/export.ics")
def cal_ics(_=Depends(need_auth)):
    from fastapi.responses import PlainTextResponse
    try:
        from app import calendar as _cal
    except ImportError:
        import sys as _s, os as _o
        _s.path.insert(0, _o.path.dirname(__file__))
        import calendar as _cal
    return PlainTextResponse(_cal.to_ics(), media_type="text/calendar",
                             headers={"Content-Disposition": "attachment; filename=osokai-calendar.ics"})

# ---- email outbox ----
@app.get("/email/outbox")
def email_list(_=Depends(need_auth)):
    try:
        from app.emailbox import outbox
    except ImportError:
        from emailbox import outbox
    return {"outbox": outbox()}

# ---- trusted sharing: osokai-to-Osok-AI encrypted bundles ----
@app.post("/share/export")
async def share_export(payload: dict, _=Depends(need_auth)):
    try:
        from app.share import export_bundle
    except ImportError:
        from share import export_bundle
    try:
        r = export_bundle(payload.get("paths", []), payload.get("note", ""))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await hub.push()
    return r

@app.post("/share/import")
async def share_import(payload: dict, _=Depends(need_auth)):
    try:
        from app.share import import_bundle
    except ImportError:
        from share import import_bundle
    r = import_bundle(payload.get("filename", ""), payload.get("content_b64", ""), payload.get("code", ""))
    if not r["ok"]:
        raise HTTPException(status_code=422, detail=r["error"])
    await hub.push()
    return r

@app.get("/share/list")
def share_list(_=Depends(need_auth)):
    try:
        from app.share import list_shared
    except ImportError:
        from share import list_shared
    return {"shared": list_shared()}

# ---- RAG: ingest + ask over workspace docs ----
@app.post("/rag/ingest")
async def rag_ingest(payload: dict, _=Depends(need_auth)):
    try:
        from app.rag import ingest
    except ImportError:
        from rag import ingest
    r = ingest(payload.get("sub", ""))
    await hub.push()
    return r

@app.post("/rag/ask")
async def rag_ask(payload: dict, _=Depends(need_auth)):
    try:
        from app.rag import search
        from app.grok_client import chat_with_grok
    except ImportError:
        from rag import search
        from grok_client import chat_with_grok
    hits = search(payload.get("q", ""), int(payload.get("k", 5)))
    if not hits:
        return {"reply": "nothing in the workspace matches that yet — ingest docs first.", "hits": []}
    ctx = "\n\n".join(f"[{h['path']}] {h['snippet']}" for h in hits)
    reply = chat_with_grok(f"Answer from these workspace excerpts (cite [path]). Q: {payload.get('q','')}\n\n{ctx[:4000]}")
    return {"reply": reply, "hits": hits}

@app.get("/rag/stats")
def rag_stats(_=Depends(need_auth)):
    try:
        from app.rag import stats
    except ImportError:
        from rag import stats
    return stats()

# ---- research + agent builder ----
@app.post("/research")
async def research_run(payload: dict, _=Depends(need_auth)):
    try:
        from app.research import deep_research
    except ImportError:
        from research import deep_research
    fp = deep_research(payload.get("topic", ""), int(payload.get("depth", 3)))
    await hub.push()
    return {"ok": True, "file": fp}

@app.post("/agents/build")
async def agents_build(payload: dict, _=Depends(need_auth)):
    try:
        from app.research import build_agent
    except ImportError:
        from research import build_agent
    r = build_agent(payload.get("name", "agent"), payload.get("purpose", ""), payload.get("tools", ""))
    await hub.push()
    return {"ok": True, "path": r}

@app.get("/agents")
def agents_list(_=Depends(need_auth)):
    try:
        from app.research import list_agents
    except ImportError:
        from research import list_agents
    return {"agents": list_agents()}

# ---- open loops: capture anywhere, close anywhere ----
def _loops():
    try:
        from app import loops as _l
    except ImportError:
        import loops as _l
    return _l

@app.get("/loops")
def loops_list(status: str = "", _=Depends(need_auth)):
    return {"loops": _loops().list_loops(status)}

@app.post("/loops")
async def loops_add(payload: dict, _=Depends(need_auth)):
    r = _loops().add(payload.get("kind", "promise"), payload.get("title", ""),
                     payload.get("source", "api"), float(payload.get("due", 0) or 0),
                     payload.get("repeat", ""))
    await hub.push()
    return r

@app.post("/loops/{lid}/close")
async def loops_close(lid: int, _=Depends(need_auth)):
    r = _loops().close(lid)
    if not r["ok"]:
        raise HTTPException(status_code=404, detail=r.get("error", "not open"))
    await hub.push()
    return r

@app.get("/loops/due")
def loops_due(_=Depends(need_auth)):
    return {"due": _loops().due_now()}

@app.post("/loops/from-approval/{aid}")
async def loops_snooze(aid: int, payload: dict = None, _=Depends(need_auth)):
    hours = 3
    try:
        hours = float((payload or {}).get("hours", 3))
    except Exception:
        pass
    r = _loops().snooze_approval(aid, hours)
    await hub.push()
    return r

@app.post("/voice/transcribe")
async def voice_transcribe(file=None, _=Depends(need_auth)):
    """Phone records, Groq whisper transcribes. Returns text ready for /chat."""
    import os as _os
    import httpx as _hx
    from fastapi import UploadFile
    if file is None or not isinstance(file, UploadFile):
        raise HTTPException(status_code=400, detail="multipart field 'file' required")
    key = _os.getenv("GROQ_API_KEY", "") or _os.getenv("GROK_API_KEY", "")
    if not key.startswith("gsk_"):
        raise HTTPException(status_code=422, detail="voice needs a Groq (gsk_) key")
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="audio too large (20MB max)")
    r = _hx.post("https://api.groq.com/openai/v1/audio/transcriptions",
                 headers={"Authorization": f"Bearer {key}"},
                 files={"file": (file.filename or "voice.m4a", data)},
                 data={"model": "whisper-large-v3-turbo"}, timeout=120)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"transcribe failed: {r.text[:200]}")
    return {"ok": True, "text": r.json().get("text", "")}

@app.get("/history/months")
def history_months(_=Depends(need_auth)):
    return mem.months_flow()

@app.get("/history/months/{ym}")
def history_month_detail(ym: str, _=Depends(need_auth)):
    d = mem.month_detail(ym)
    return {**d, "days": mem.month_days(ym), "total": d["tasks"]}

@app.get("/history")
def history_month(month: str = "", _=Depends(need_auth)):
    import datetime
    if not month:
        now = datetime.datetime.now()
        month = f"{now.year:04d}-{now.month:02d}"
    return mem.month_detail(month)

@app.get("/files")
def files(path: str = "", _=Depends(need_auth)):
    return {"path": path, "workspace": mem.list_files(path), "entries": mem.list_entries(path)}

@app.get("/connectors")
def connectors(_=Depends(need_auth)):
    return {"connectors": list_connectors(), "add_more": True}

@app.get("/connectors/{cid}/auth-url")
def connector_auth(cid: str, _=Depends(need_auth)):
    return {"id": cid, **auth_url(cid)}

@app.post("/connectors/{cid}/connect")
async def connector_connect(cid: str, payload: dict, _=Depends(need_auth)):
    r = connect(cid, payload)
    await hub.push()
    return r

@app.post("/connectors/{cid}/disconnect")
async def connector_disconnect(cid: str, _=Depends(need_auth)):
    r = disconnect(cid)
    await hub.push()
    return r

# ---- bills: shared expenses tracker ----
@app.post("/bills/groups")
async def bills_mkgroup(payload: dict, _=Depends(need_auth)):
    try:
        from app.bills import create_group
    except ImportError:
        from bills import create_group
    r = create_group(payload.get("name", "group"), payload.get("members", []))
    await hub.push()
    return r

@app.get("/bills/groups")
def bills_groups(_=Depends(need_auth)):
    try:
        from app.bills import list_groups
    except ImportError:
        from bills import list_groups
    return {"groups": list_groups()}

@app.post("/bills/expenses")
async def bills_expense(payload: dict, _=Depends(need_auth)):
    try:
        from app.bills import add_expense
    except ImportError:
        from bills import add_expense
    r = add_expense(int(payload.get("gid", 0)), payload.get("title", ""), float(payload.get("amount", 0)),
                    payload.get("paid_by", ""), payload.get("splits") or {})
    await hub.push()
    return r

@app.get("/bills/balances/{gid}")
def bills_bal(gid: int, _=Depends(need_auth)):
    try:
        from app.bills import balances
    except ImportError:
        from bills import balances
    return balances(gid)

@app.post("/bills/settle")
async def bills_settle(payload: dict, _=Depends(need_auth)):
    try:
        from app.bills import settle
    except ImportError:
        from bills import settle
    r = settle(int(payload.get("gid", 0)), payload.get("frm", ""), payload.get("to", ""), float(payload.get("amount", 0)))
    await hub.push()
    return r

@app.get("/bills/activity/{gid}")
def bills_act(gid: int, _=Depends(need_auth)):
    try:
        from app.bills import activity
    except ImportError:
        from bills import activity
    return {"activity": activity(gid)}

# ---- wardrobe: outfit planner ----
def _w():
    try:
        from app import wardrobe as w
    except ImportError:
        import wardrobe as w
    return w

@app.get("/wardrobe/items")
def w_items(_=Depends(need_auth)):
    return {"items": _w().list_items()}

@app.post("/wardrobe/items")
async def w_add(payload: dict, _=Depends(need_auth)):
    w = _w()
    r = w.add_item(payload.get("category", ""), payload.get("color", ""),
                   payload.get("season", "all"), payload.get("formality", "casual"))
    await hub.push()
    return r

@app.get("/wardrobe/suggest")
def w_suggest(formality: str = "", _=Depends(need_auth)):
    return _w().suggest(formality=formality)

@app.post("/wardrobe/worn/{iid}")
async def w_worn(iid: int, _=Depends(need_auth)):
    r = _w().mark_worn(iid)
    await hub.push()
    return r

@app.post("/wardrobe/feedback")
async def w_feedback(payload: dict, _=Depends(need_auth)):
    r = _w().feedback(int(payload.get("id", 0)), bool(payload.get("good", True)), payload.get("note", ""))
    await hub.push()
    return r

@app.get("/wardrobe/prefs")
def w_prefs(_=Depends(need_auth)):
    return {"prefs": _w().get_prefs()}

@app.patch("/connectors/{cid}")
async def connector_patch(cid: str, payload: dict, _=Depends(need_auth)):
    if "enabled" in payload:
        r = set_enabled(cid, payload["enabled"])
        await hub.push()
        return r
    return refresh(cid)

@app.post("/connectors/{cid}/refresh")
async def connector_refresh(cid: str, _=Depends(need_auth)):
    return refresh(cid)

@app.get("/connectors/{cid}/login")
def connector_login(cid: str, _=Depends(need_auth)):
    """One-click OAuth start. Needs CLIENT_ID/SECRET in .env or says exactly what's missing."""
    try:
        from app.oauth import authorize_url
    except ImportError:
        from oauth import authorize_url
    try:
        url = authorize_url(cid)
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    try:
        from app.system_tools import open_url
    except ImportError:
        from system_tools import open_url
    open_url(url)
    return {"ok": True, "login_url": url}

# ---- goals: recurring watches with deduped alerts ----
@app.post("/goals")
async def goals_mk(payload: dict, _=Depends(need_auth)):
    try:
        from app.goals import create, start_loop
    except ImportError:
        from goals import create, start_loop
    r = create(payload.get("title", "watch"), payload.get("url", ""), payload.get("kind", "change"), payload.get("target", ""))
    start_loop(hub.push)
    await hub.push()
    return r

@app.get("/goals")
def goals_list(_=Depends(need_auth)):
    try:
        from app.goals import list_all
    except ImportError:
        from goals import list_all
    return {"goals": list_all()}

@app.delete("/goals/{gid}")
async def goals_del(gid: int, _=Depends(need_auth)):
    try:
        from app.goals import remove
    except ImportError:
        from goals import remove
    r = remove(gid)
    await hub.push()
    return r

@app.post("/goals/{gid}/check")
async def goals_check(gid: int, _=Depends(need_auth)):
    try:
        from app.goals import check_once
    except ImportError:
        from goals import check_once
    new = check_once(gid)
    if new:
        await hub.push()
    return {"alerts": new}

@app.get("/goals/alerts")
def goals_alerts(_=Depends(need_auth)):
    try:
        from app.goals import alerts
    except ImportError:
        from goals import alerts
    return {"alerts": alerts()}

# ---- browser takeover console ----
@app.get("/browser/state")
def browser_state(_=Depends(need_auth)):
    try:
        from app.browser_ctl import state
    except ImportError:
        from browser_ctl import state
    return {"state": state()}

@app.get("/browser/screenshot")
def browser_shot(_=Depends(need_auth)):
    from fastapi.responses import FileResponse
    try:
        from app.browser_ctl import screenshot
    except ImportError:
        from browser_ctl import screenshot
    fp = screenshot()
    if not fp:
        raise HTTPException(status_code=502, detail="browser screenshot failed — is browser-use installed?")
    return FileResponse(fp, media_type="image/png")

@app.get("/connectors/callback")
async def connector_callback(provider: str = "", code: str = ""):
    """OAuth landing: exchanges code, encrypts tokens, marks connected. No auth header (browser redirect)."""
    if not provider or not code:
        raise HTTPException(status_code=400, detail="missing provider/code")
    try:
        from app.oauth import exchange
        from app.connectors import oauth_store
    except ImportError:
        from oauth import exchange
        from connectors import oauth_store
    try:
        tokens = exchange(provider, code)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"token exchange failed: {e}")
    oauth_store(provider, tokens)
    await hub.push()
    return {"ok": True, "provider": provider, "connected": True,
            "msg": "Connected — you can close this tab and return to Osok-AI."}

@app.get("/inbox")
def inbox(_=Depends(need_auth)):
    return {"summary": inbox_summary()}

@app.get("/notifications")
def notes(_=Depends(need_auth)):
    n = notifications()
    try:
        from app.goals import alerts
    except ImportError:
        from goals import alerts
    ga = alerts(unseen_only=True)
    n["alerts"] = ga
    n["unread"] = n.get("unread", 0) + len(ga)
    return n

@app.post("/notifications/simulate")
async def notes_sim(payload: dict, _=Depends(need_auth)):
    r = simulate(payload.get("unread", 0), payload.get("from", "test"))
    await hub.push()
    return r

@app.websocket("/ws/sync")
async def ws_sync(ws: WebSocket):
    import asyncio as _aio
    want = os.getenv("OSOKAI_AUTH_TOKEN", "")
    if want and ws.query_params.get("token") != want:
        await ws.close(code=4401)
        return
    await hub.add(ws)
    try:
        while True:
            try:
                await _aio.wait_for(ws.receive_text(), timeout=25)
            except _aio.TimeoutError:
                try:
                    await ws.send_json({"ping": True, "rev": hub.rev})
                except Exception:
                    break
    except WebSocketDisconnect as e:
        print(f"ws closed code={e.code}", flush=True)
        hub.drop(ws)
    except Exception as e:
        print(f"ws error {type(e).__name__}: {e}", flush=True)
        hub.drop(ws)
