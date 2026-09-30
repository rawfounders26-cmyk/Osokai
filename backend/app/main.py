"""Osok-AI backend — FastAPI gateway. All frontends talk here + stay in sync via /ws/sync."""
import os, time
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Header, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from app.paths import env_file as _env_file
except ImportError:
    from paths import env_file as _env_file
load_dotenv(_env_file())

def _ensure_auth_token():
    """Packaged app: no open-auth dev mode. Generate once into .env next to the exe."""
    if os.getenv("OSOKAI_AUTH_TOKEN", ""):
        return
    import secrets as _s
    new = "osokai_" + _s.token_urlsafe(24)
    try:
        open(_env_file(), "a").write(f"OSOKAI_AUTH_TOKEN={new}\n")
    except Exception:
        pass
    os.environ["OSOKAI_AUTH_TOKEN"] = new

_ensure_auth_token()
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
_cors = [o.strip() for o in os.getenv("OSOKAI_CORS", "*").split(",") if o.strip()] or ["*"]
app.add_middleware(CORSMiddleware, allow_origins=_cors, allow_methods=["*"], allow_headers=["*"])
mem = Memory()

OSOKAI_VERSION = "0.6.0"

# ---- reliability: request ids + per-IP rate limiting (abuse shield) ----
import uuid as _uuid
from fastapi.responses import JSONResponse as _JSONResponse
_rl_hits: dict = {}

@app.middleware("http")
async def _reliability(request: Request, call_next):
    rid = _uuid.uuid4().hex[:8]
    ip = request.client.host if request.client else "?"
    now = time.time()
    heavy = request.url.path.startswith(("/chat", "/goaltrees/tasks", "/research"))
    limit, window = (60, 60) if heavy else (600, 60)
    bucket = _rl_hits.setdefault(ip, [])
    while bucket and bucket[0] < now - window:
        bucket.pop(0)
    if len(bucket) >= limit:
        return _JSONResponse({"detail": "rate limited — slow down"}, status_code=429,
                             headers={"X-Request-Id": rid})
    bucket.append(now)
    try:
        resp = await call_next(request)
    except Exception:
        return _JSONResponse({"detail": "internal error", "request_id": rid}, status_code=500)
    resp.headers["X-Request-Id"] = rid
    return resp

@app.on_event("startup")
async def _start_proactive():
    import asyncio as _aio
    try:
        try:
            from app.proactive import loop as _ploop
            from app.schedules import loop as _sloop
        except ImportError:
            from proactive import loop as _ploop
            from schedules import loop as _sloop
        _aio.create_task(_ploop())
        _aio.create_task(_sloop())
    except Exception:
        pass

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
_pairings = {}  # code -> {url, exp} (5-min TTL, in-memory by design)

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

def _fillq():
    try:
        from app import fillq as _f
    except ImportError:
        import fillq as _f
    return _f

@app.post("/fill/request")
async def fill_request(payload: dict, _=Depends(need_auth)):
    r = _fillq().request_fill(payload.get("site", ""), payload.get("fields", "login"))
    await hub.push()
    return r

@app.get("/fill/pending")
def fill_pending(domain: str = "", _=Depends(need_auth)):
    return {"pending": _fillq().pending_for(domain)}

@app.post("/fill/{fid}/done")
async def fill_done(fid: int, _=Depends(need_auth)):
    r = _fillq().mark(fid, "done")
    await hub.push()
    return r

@app.post("/fill/{fid}/captcha")
async def fill_captcha(fid: int, _=Depends(need_auth)):
    r = _fillq().mark(fid, "captcha")
    await hub.push()
    return r

@app.post("/fill/{fid}/solved")
async def fill_solved(fid: int, _=Depends(need_auth)):
    r = _fillq().mark(fid, "pending")
    await hub.push()
    return r

@app.post("/fill/{fid}/otp")
async def fill_otp(fid: int, _=Depends(need_auth)):
    """Extension pulls + burns the user-pasted OTP for this fill."""
    return {"ok": True, "otp": _fillq().take_otp(fid)}

@app.post("/pairing/code")
async def pairing_code(payload: dict, _=Depends(need_auth)):
    """Desktop shows a 6-char code; phone enters it instead of pasting URL+token. 5-min TTL."""
    import secrets as _s
    import socket as _so
    code = "".join(_s.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(6))
    url = (payload.get("url") or "").replace("127.0.0.1", "").replace("localhost", "")
    if not url:
        try:
            s = _so.socket(_so.AF_INET, _so.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            url = f"http://{s.getsockname()[0]}:8765"
            s.close()
        except Exception:
            url = ""
    else:
        import re as _re
        m = _re.search(r":(\d+)", payload.get("url", ""))
        port = m.group(1) if m else "8765"
        try:
            s = _so.socket(_so.AF_INET, _so.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            url = f"http://{s.getsockname()[0]}:{port}"
            s.close()
        except Exception:
            pass
    _pairings[code] = {"url": url, "exp": time.time() + 300}
    for k in [k for k, v in _pairings.items() if v["exp"] < time.time()]:
        _pairings.pop(k, None)
    return {"ok": True, "code": code, "url": url}

@app.post("/pairing/redeem")
def pairing_redeem(payload: dict):
    """No auth (the code IS the auth). Returns URL + token once, then burns."""
    code = (payload.get("code") or "").strip().upper()
    rec = _pairings.pop(code, None)
    if not rec or rec["exp"] < time.time():
        raise HTTPException(status_code=404, detail="bad or expired code")
    return {"ok": True, "url": rec["url"], "token": os.getenv("OSOKAI_AUTH_TOKEN", "")}

@app.post("/chat")
async def chat(body: ChatIn, _=Depends(need_auth)):
    try:
        from app.system_tools import sanitize_reply as _san
    except ImportError:
        from system_tools import sanitize_reply as _san
    # bare OTP paste: 4-8 digits go to the newest pending fill (encrypted, single-use)
    import re as _re2
    if _re2.match(r"^\d{4,8}$", body.message.strip()):
        r = _fillq().set_otp(body.message.strip())
        if r:
            mem.add("user", "[otp pasted — value hidden]")
            mem.add("Osok-AI", "OTP saved — the extension will fill it.")
            await hub.push()
            return {"reply": "OTP saved — the extension will fill it.", "approval_required": False, "action": "otp"}
    # local-first fast lane: trivial answers never cost tokens or latency
    try:
        from app.local import try_answer as _local_ans
    except ImportError:
        from local import try_answer as _local_ans
    _loc = _local_ans(body.message)
    try:
        from app.usage import set_actor as _set_actor
    except ImportError:
        try:
            from usage import set_actor as _set_actor
        except ImportError:
            _set_actor = lambda *a: None
    _set_actor(body.device)
    if _loc:
        mem.add("user", body.message)
        mem.add("Osok-AI", _loc)
        try:
            from app.usage import log as _ulog
        except ImportError:
            from usage import log as _ulog
        _ulog("local", "on-device", body.message, _loc, 0, tokens=0)
        await hub.push()
        return {"reply": _loc, "approval_required": False, "action": "local"}
    # loops capture first: "remind me to pay X" is a reminder, not a payment
    _pre, _ = intent_parse(body.message)
    if _pre and _pre.get("type") in ("loop_add", "loop_done"):
        mem.add("user", body.message)
        reply = _san(intent_run(_pre, body.device))
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
    # outfit/bills fast intents run before calendar (else "add X to wardrobe" becomes an event)
    _pre, _ = intent_parse(body.message)
    if _pre and _pre.get("type", "").startswith(("outfit_", "bill_")):
        mem.add("user", body.message)
        reply = _san(intent_run(_pre, body.device))
        mem.add("Osok-AI", reply)
        await hub.push()
        return {"reply": reply, "approval_required": False, "action": _pre["type"]}
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
        reply = _san(intent_run(action, body.device))
        mem.add("Osok-AI", reply)
        await hub.push()
        out = {"reply": reply, "approval_required": False, "action": action["type"]}
        if action["type"] in ("youtube_play", "shop_browse", "open_url"):
            out["url"] = action.get("url", "")  # mobile opens directly / links it
        return out
    # big multi-step goal from chat -> compile a goal tree (agent decides goal vs task here)
    try:
        from app.agent import is_big_goal as _is_big
    except ImportError:
        from agent import is_big_goal as _is_big
    if _is_big(body.message):
        try:
            from app import goaltrees as _gtm
        except ImportError:
            import goaltrees as _gtm
        mem.add("user", body.message)
        r = _gtm.compile_goal(body.message.strip())
        t = _gtm.get_tree(r["id"]) if r else None
        n = sum(len(p["tasks"]) for o in (t["objectives"] if t else []) for p in o["projects"]) if t else 0
        reply = f"Goal created: {body.message.strip()} ({len(t['objectives']) if t else 0} objectives, {n} tasks) — see Goals screen."
        mem.add("Osok-AI", reply)
        await hub.push()
        return {"reply": reply, "approval_required": False, "action": "goal", "goal_id": r["id"] if r else None}
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
            reply = _san(await asyncio.to_thread(agent_run, body.message))
            _runs.log_step(rid, "tools finished", 90)
            _runs.complete(rid, reply)
        except Exception as e:
            reply = f"[osok-ai-error] {e}"
            _runs.complete(rid, reply, "failed")
        mem.add("Osok-AI", reply)
        await hub.push()
        return {"reply": reply, "approval_required": False, "action": "agent", "run_id": rid}
    mem.add("user", body.message)
    # SLM-zone: on-device weights answer when ready, Groq otherwise (optimizer routes)
    try:
        from app.local import confidence as _conf
        from app.slm import status as _slm_status, generate as _slm_gen
        from app.optimizer import recommend as _rec
        from app.usage import log as _ulog2
    except ImportError:
        from local import confidence as _conf
        from slm import status as _slm_status, generate as _slm_gen
        from optimizer import recommend as _rec
        from usage import log as _ulog2
    _route = _rec("chat", _conf(body.message), bool(_slm_status()["available"]))
    if _route["route"] == "slm":
        try:
            import asyncio as _aio_slm
            reply = _san(await _aio_slm.to_thread(_slm_gen, body.message))
            mem.add("Osok-AI", reply)
            _ulog2("slm", "on-device", body.message, reply, 0, tokens=0)
            await hub.push()
            return {"reply": reply, "approval_required": False, "action": "slm"}
        except Exception:
            pass  # weights hiccup -> fall through to Groq
    reply = _san(chat_with_grok(body.message))
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

# ---- goal trees: Goal → Objectives → Projects → Tasks ----
def _gt():
    try:
        from app import goaltrees as _g
    except ImportError:
        import goaltrees as _g
    return _g

@app.get("/goaltrees")
def gt_list(_=Depends(need_auth)):
    return {"goals": _gt().list_trees()}

@app.post("/goaltrees/template")
async def gt_template(payload: dict, _=Depends(need_auth)):
    r = _gt().create_from_template(payload.get("key", ""), payload.get("title", ""))
    if not r["ok"]:
        raise HTTPException(status_code=400, detail=r["error"])
    await hub.push()
    return r

@app.post("/goaltrees/compile")
async def gt_compile(payload: dict, _=Depends(need_auth)):
    if not payload.get("title", "").strip():
        raise HTTPException(status_code=400, detail="title required")
    r = _gt().compile_goal(payload["title"].strip())
    await hub.push()
    return r

@app.get("/goaltrees/{gid}")
def gt_get(gid: int, _=Depends(need_auth)):
    t = _gt().get_tree(gid)
    if not t:
        raise HTTPException(status_code=404, detail="goal not found")
    return t

@app.post("/goaltrees/tasks/{tid}/run")
async def gt_run(tid: int, payload: dict = None, _=Depends(need_auth)):
    import asyncio as _aio
    gt = _gt()
    r = await _aio.to_thread(gt.run_task, tid, (payload or {}).get("device", "api"))
    await hub.push()
    return r

# ---- orchestrator: autonomous planner -> executor -> critic steps ----
@app.post("/goaltrees/{gid}/auto-step")
async def gt_auto_step(gid: int, payload: dict = None, _=Depends(need_auth)):
    import asyncio as _aio
    try:
        from app.orchestrator import auto_step
    except ImportError:
        from orchestrator import auto_step
    r = await _aio.to_thread(auto_step, gid, (payload or {}).get("device", "orchestrator"))
    await hub.push()
    return r

@app.get("/goaltrees/{gid}/history")
def gt_orch_history(gid: int, _=Depends(need_auth)):
    try:
        from app.orchestrator import history
    except ImportError:
        from orchestrator import history
    return {"history": history(gid)}

# ---- profile: identity (never secrets) ----
def _prof():
    try:
        from app import profile as _p
    except ImportError:
        import profile as _p
    return _p

@app.get("/profile")
def profile_get(_=Depends(need_auth)):
    return {"profile": _prof().get_profile(), "prefs": _prof().get_prefs()}

@app.post("/profile")
async def profile_set(payload: dict, _=Depends(need_auth)):
    r = _prof().set_profile(payload.get("key", ""), payload.get("value", ""))
    if not r["ok"]:
        raise HTTPException(status_code=400, detail=r["error"])
    await hub.push()
    return r

@app.post("/profile/prefs")
async def profile_pref(payload: dict, _=Depends(need_auth)):
    r = _prof().add_pref(payload.get("domain", "general"), payload.get("pref", ""))
    await hub.push()
    return r

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

@app.post("/rag/answer")
async def rag_answer(payload: dict, _=Depends(need_auth)):
    """Grounded Q&A: hybrid retrieval + synthesized reply with citations."""
    try:
        from app.rag import answer
    except ImportError:
        from rag import answer
    return answer(payload.get("q", ""), int(payload.get("k", 5)))

# ---- proactive nudges: the agent tapping your shoulder ----
@app.get("/nudges")
def nudges_list(unseen: bool = True, _=Depends(need_auth)):
    try:
        from app.proactive import list_nudges
    except ImportError:
        from proactive import list_nudges
    return {"nudges": list_nudges(unseen_only=unseen)}

@app.post("/nudges/seen")
async def nudges_seen(payload: dict = None, _=Depends(need_auth)):
    try:
        from app.proactive import mark_seen
    except ImportError:
        from proactive import mark_seen
    r = mark_seen(int((payload or {}).get("id", 0)))
    await hub.push()
    return r

# ---- memory 2.0: facts + recall + rolling summary ----
@app.post("/memory/facts")
async def memory_fact(payload: dict, _=Depends(need_auth)):
    fid = mem.note_fact(payload.get("fact", ""), float(payload.get("salience", 1.0)))
    await hub.push()
    return {"ok": True, "id": fid}

@app.get("/memory/recall")
def memory_recall(q: str = "", k: int = 5, _=Depends(need_auth)):
    return {"facts": mem.recall(q, k), "summary": mem.get_summary()}

# ---- device presence + offline outbox ----
@app.post("/devices/heartbeat")
async def device_beat(payload: dict, _=Depends(need_auth)):
    try:
        from app.presence import heartbeat
    except ImportError:
        from presence import heartbeat
    return heartbeat(payload.get("device", "unknown"), payload.get("meta", ""))

@app.get("/devices")
def devices_list(_=Depends(need_auth)):
    try:
        from app.presence import list_devices
    except ImportError:
        from presence import list_devices
    return {"devices": list_devices()}

@app.get("/updates/latest")
def updates_latest():
    return {"version": OSOKAI_VERSION, "notes": "See GitHub releases for changelog."}

# ---- usage + cost dashboard ----
@app.get("/usage/summary")
def usage_summary(days: int = 30, _=Depends(need_auth)):
    try:
        from app.usage import summary
    except ImportError:
        from usage import summary
    return summary(days)

@app.post("/usage/budget")
async def usage_budget(payload: dict, _=Depends(need_auth)):
    try:
        from app.usage import set_budget
    except ImportError:
        from usage import set_budget
    r = set_budget(float(payload.get("monthly_cap_usd", 0)))
    await hub.push()
    return r

# ---- skill marketplace: signed community packs ----
@app.get("/marketplace")
def market_list(_=Depends(need_auth)):
    try:
        from app.marketplace import list_market
    except ImportError:
        from marketplace import list_market
    return {"packs": list_market()}

@app.post("/marketplace/install")
async def market_install(payload: dict, _=Depends(need_auth)):
    try:
        from app.marketplace import install
    except ImportError:
        from marketplace import install
    r = install(payload.get("name", ""), bool(payload.get("ack_high_risk", False)))
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("error", "install failed"))
    await hub.push()
    return r

@app.post("/marketplace/enable")
async def market_enable(payload: dict, _=Depends(need_auth)):
    try:
        from app.marketplace import set_enabled
    except ImportError:
        from marketplace import set_enabled
    r = set_enabled(payload.get("name", ""), bool(payload.get("enabled", True)))
    await hub.push()
    return r

@app.post("/marketplace/uninstall")
async def market_uninstall(payload: dict, _=Depends(need_auth)):
    try:
        from app.marketplace import uninstall
    except ImportError:
        from marketplace import uninstall
    r = uninstall(payload.get("name", ""))
    await hub.push()
    return r

# ---- team mode: shared goals + multi-user approvals ----
@app.post("/teams")
async def team_create(payload: dict, _=Depends(need_auth)):
    try:
        from app.teams import create_team
    except ImportError:
        from teams import create_team
    r = create_team(payload.get("name", "team"), payload.get("owner", "me"))
    await hub.push()
    return r

@app.get("/teams")
def teams_list(_=Depends(need_auth)):
    try:
        from app.teams import list_teams
    except ImportError:
        from teams import list_teams
    return {"teams": list_teams()}

@app.post("/teams/{tid}/members")
async def team_add(tid: int, payload: dict, _=Depends(need_auth)):
    try:
        from app.teams import add_member
    except ImportError:
        from teams import add_member
    r = add_member(tid, payload.get("user", ""), payload.get("role", "member"))
    if not r.get("ok"):
        raise HTTPException(status_code=404, detail=r.get("error", "no such team"))
    await hub.push()
    return r

@app.post("/teams/{tid}/share-goal")
async def team_share(tid: int, payload: dict, _=Depends(need_auth)):
    try:
        from app.teams import share_goal
    except ImportError:
        from teams import share_goal
    r = share_goal(int(payload.get("gid", 0)), tid)
    if not r.get("ok"):
        raise HTTPException(status_code=404, detail=r.get("error", "no such team"))
    await hub.push()
    return r

@app.get("/teams/{tid}/goals")
def team_goals_list(tid: int, _=Depends(need_auth)):
    try:
        from app.teams import team_goals
    except ImportError:
        from teams import team_goals
    return {"goals": team_goals(tid)}

@app.post("/teams/{tid}/ask")
async def team_ask(tid: int, payload: dict, _=Depends(need_auth)):
    try:
        from app.teams import ask_team
    except ImportError:
        from teams import ask_team
    r = ask_team(tid, payload.get("message", ""), payload.get("kind", "general"), payload.get("item", ""))
    await hub.push()
    return r

@app.get("/teams/{tid}/pending")
def team_pending_list(tid: int, _=Depends(need_auth)):
    try:
        from app.teams import team_pending
    except ImportError:
        from teams import team_pending
    return {"pending": team_pending(tid)}

@app.post("/teams/approvals/{aid}/resolve")
async def team_resolve(aid: int, payload: dict, _=Depends(need_auth)):
    try:
        from app.teams import team_resolve
    except ImportError:
        from teams import team_resolve
    r = team_resolve(aid, payload.get("user", "me"), bool(payload.get("allow", False)))
    if not r.get("ok"):
        raise HTTPException(status_code=403, detail=r.get("error", "denied"))
    await hub.push()
    return r

# ---- voice loop: one-call command + spoken reply ----
@app.post("/voice/command")
async def voice_command(payload: dict, _=Depends(need_auth)):
    """Voice-optimized chat: same brain, short spoken-style replies."""
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    try:
        from app.local import try_answer as _local_ans
    except ImportError:
        from local import try_answer as _local_ans
    loc = _local_ans(text)
    if loc:
        return {"reply": loc, "action": "local", "speak": True}
    try:
        from app.intents import parse as _parse, execute as _run
        from app.system_tools import sanitize_reply as _san
    except ImportError:
        from intents import parse as _parse, execute as _run
        from system_tools import sanitize_reply as _san
    pre, _ = _parse(text)
    if pre and pre.get("type") not in ("loop_add", "loop_done"):
        mem.add("user", "[voice] " + text)
        reply = _san(_run(pre, payload.get("device", "voice")))
        mem.add("Osok-AI", reply)
        await hub.push()
        return {"reply": reply, "action": pre.get("type"), "speak": True}
    reply = chat_with_grok("Reply in ONE short spoken sentence, no lists: " + text)
    mem.add("user", "[voice] " + text)
    mem.add("Osok-AI", reply)
    await hub.push()
    return {"reply": reply, "action": "chat", "speak": True}

@app.post("/voice/speak")
def voice_speak(payload: dict, _=Depends(need_auth)):
    """Speak text aloud on the host. Needs `pip install pyttsx3` (Windows SAPI)."""
    text = (payload.get("text") or "")[:500]
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    try:
        import pyttsx3 as _tts
    except ImportError:
        return {"ok": False, "error": "TTS not installed — run: pip install pyttsx3"}
    try:
        eng = _tts.init()
        eng.say(text)
        eng.runAndWait()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": f"TTS failed: {e}"}

# ---- v0.4: scheduled autonomy ----
@app.post("/schedules")
async def sched_create(payload: dict, _=Depends(need_auth)):
    try:
        from app.schedules import create
    except ImportError:
        from schedules import create
    r = create(payload.get("name", "job"), payload.get("kind", ""),
               payload.get("args", {}), payload.get("at_time", ""), int(payload.get("every_min", 0)))
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("error", "bad job"))
    await hub.push()
    return r

@app.get("/schedules")
def sched_list(_=Depends(need_auth)):
    try:
        from app.schedules import list_jobs
    except ImportError:
        from schedules import list_jobs
    return {"jobs": list_jobs()}

@app.post("/schedules/{jid}/enable")
async def sched_enable(jid: int, payload: dict, _=Depends(need_auth)):
    try:
        from app.schedules import set_enabled
    except ImportError:
        from schedules import set_enabled
    r = set_enabled(jid, bool(payload.get("enabled", True)))
    await hub.push()
    return r

@app.post("/schedules/{jid}/run-now")
async def sched_run_now(jid: int, _=Depends(need_auth)):
    import asyncio as _aio
    try:
        from app.schedules import list_jobs, execute, _log_run
    except ImportError:
        from schedules import list_jobs, execute, _log_run
    job = next((j for j in list_jobs() if j["id"] == jid), None)
    if not job:
        raise HTTPException(status_code=404, detail="no such job")
    r = await _aio.to_thread(execute, job)
    await _aio.to_thread(_log_run, jid, r["ok"], r["note"])
    await hub.push()
    return r

@app.delete("/schedules/{jid}")
async def sched_delete(jid: int, _=Depends(need_auth)):
    try:
        from app.schedules import remove
    except ImportError:
        from schedules import remove
    r = remove(jid)
    await hub.push()
    return r

@app.get("/schedules/{jid}/runs")
def sched_runs(jid: int, _=Depends(need_auth)):
    try:
        from app.schedules import runs
    except ImportError:
        from schedules import runs
    return {"runs": runs(jid)}

# ---- v0.4: sandbox gates + reputation ----
@app.get("/sandbox/perms")
def sandbox_perms(_=Depends(need_auth)):
    try:
        from app.sandbox import KNOWN_PERMS
    except ImportError:
        from sandbox import KNOWN_PERMS
    return {"perms": [{"perm": k, "risk": v} for k, v in KNOWN_PERMS.items()]}

@app.get("/sandbox/grants/{skill}")
def sandbox_grants(skill: str, _=Depends(need_auth)):
    try:
        from app.sandbox import grants_for
    except ImportError:
        from sandbox import grants_for
    return {"skill": skill, "grants": grants_for(skill)}

@app.post("/sandbox/check")
def sandbox_check(payload: dict, _=Depends(need_auth)):
    try:
        from app.sandbox import check
    except ImportError:
        from sandbox import check
    return {"skill": payload.get("skill", ""), "perm": payload.get("perm", ""),
            "allowed": check(payload.get("skill", ""), payload.get("perm", ""))}

@app.post("/marketplace/rate")
async def market_rate(payload: dict, _=Depends(need_auth)):
    try:
        from app.sandbox import rate
    except ImportError:
        from sandbox import rate
    return rate(payload.get("name", ""), payload.get("user", "me"), int(payload.get("stars", 5)))

@app.get("/marketplace/reputation/{skill}")
def market_rep(skill: str, _=Depends(need_auth)):
    try:
        from app.sandbox import reputation
    except ImportError:
        from sandbox import reputation
    return reputation(skill)

# ---- v0.4: team roles, budgets, per-seat spend ----
@app.post("/teams/{tid}/role")
async def team_role(tid: int, payload: dict, _=Depends(need_auth)):
    try:
        from app.teams import set_role
    except ImportError:
        from teams import set_role
    r = set_role(tid, payload.get("admin", "me"), payload.get("user", ""), payload.get("role", "member"))
    if not r.get("ok"):
        raise HTTPException(status_code=403, detail=r.get("error", "denied"))
    await hub.push()
    return r

@app.post("/teams/{tid}/budget")
async def team_budget(tid: int, payload: dict, _=Depends(need_auth)):
    try:
        from app.teams import set_budget
    except ImportError:
        from teams import set_budget
    r = set_budget(tid, payload.get("admin", "me"), float(payload.get("cap_usd", 0)))
    if not r.get("ok"):
        raise HTTPException(status_code=403, detail=r.get("error", "denied"))
    await hub.push()
    return r

@app.get("/teams/{tid}/spend")
def team_spend(tid: int, _=Depends(need_auth)):
    try:
        from app.teams import spend
    except ImportError:
        from teams import spend
    return spend(tid)

# ---- v0.4: E2E relay-lite (sealed envelopes) ----
@app.post("/relay/push")
async def relay_push(payload: dict, _=Depends(need_auth)):
    try:
        from app.relay import seal
    except ImportError:
        from relay import seal
    if not payload.get("device") or "payload" not in payload:
        raise HTTPException(status_code=400, detail="device + payload required")
    return seal(payload["device"], payload["payload"])

@app.get("/relay/pull")
def relay_pull(device: str, _=Depends(need_auth)):
    try:
        from app.relay import pull
    except ImportError:
        from relay import pull
    return {"envelopes": pull(device)}

# ---- v0.4: voice sessions (chunked audio -> transcribe -> command) ----
_voice_sessions: dict = {}

@app.post("/voice/session/start")
async def voice_sess_start(payload: dict = None, _=Depends(need_auth)):
    import uuid as _u
    sid = _u.uuid4().hex[:12]
    _voice_sessions[sid] = {"chunks": [], "ts": time.time()}
    return {"ok": True, "session": sid}

@app.post("/voice/session/chunk")
async def voice_sess_chunk(payload: dict, _=Depends(need_auth)):
    import base64 as _b64
    sid = payload.get("session", "")
    s = _voice_sessions.get(sid)
    if not s:
        raise HTTPException(status_code=404, detail="no such session")
    try:
        s["chunks"].append(_b64.b64decode(payload.get("audio_b64", "")))
    except Exception:
        raise HTTPException(status_code=400, detail="bad audio_b64")
    if sum(len(c) for c in s["chunks"]) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="audio too large (20MB max)")
    s["ts"] = time.time()
    return {"ok": True, "bytes": sum(len(c) for c in s["chunks"])}

@app.post("/voice/session/finish")
async def voice_sess_finish(payload: dict, _=Depends(need_auth)):
    import httpx as _hx
    sid = payload.get("session", "")
    s = _voice_sessions.pop(sid, None)
    if not s or not s["chunks"]:
        raise HTTPException(status_code=404, detail="no such session or empty")
    key = os.getenv("GROQ_API_KEY", "") or os.getenv("GROK_API_KEY", "")
    if not key.startswith("gsk_"):
        raise HTTPException(status_code=422, detail="voice needs a Groq (gsk_) key")
    data = b"".join(s["chunks"])
    r = _hx.post("https://api.groq.com/openai/v1/audio/transcriptions",
                 headers={"Authorization": f"Bearer {key}"},
                 files={"file": ("voice.m4a", data)},
                 data={"model": "whisper-large-v3-turbo"}, timeout=120)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"transcribe failed: {r.text[:200]}")
    text = r.json().get("text", "")
    return {"ok": True, "text": text,
            "command": {"hint": "POST this text to /voice/command", "text": text}}

# ---- v0.5: client-held E2E (server stores pubkeys + blind ciphertext only) ----
@app.post("/e2e/register")
async def e2e_register(payload: dict, _=Depends(need_auth)):
    try:
        from app.e2e import register
    except ImportError:
        from e2e import register
    r = register(payload.get("device", ""), payload.get("pubkey", ""))
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("error", "bad key"))
    await hub.push()
    return r

@app.get("/e2e/directory")
def e2e_directory(_=Depends(need_auth)):
    try:
        from app.e2e import directory
    except ImportError:
        from e2e import directory
    return {"devices": directory()}

@app.post("/e2e/push")
async def e2e_push(payload: dict, _=Depends(need_auth)):
    try:
        from app.e2e import push_envelope
    except ImportError:
        from e2e import push_envelope
    r = push_envelope(payload.get("device", ""), payload.get("envelope", {}))
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("error", "bad envelope"))
    return r

@app.get("/e2e/pull")
def e2e_pull(device: str, _=Depends(need_auth)):
    try:
        from app.e2e import pull_envelopes
    except ImportError:
        from e2e import pull_envelopes
    return {"envelopes": pull_envelopes(device)}

# ---- v0.5: SLM slot ----
@app.get("/slm/status")
def slm_status(_=Depends(need_auth)):
    try:
        from app.slm import status
    except ImportError:
        from slm import status
    return status()

# ---- v0.5: wake-word config + streaming voice ----
@app.get("/voice/wake-config")
def wake_get(_=Depends(need_auth)):
    try:
        from app.wake import get_config
    except ImportError:
        from wake import get_config
    return get_config()

@app.post("/voice/wake-config")
async def wake_set(payload: dict, _=Depends(need_auth)):
    try:
        from app.wake import set_config
    except ImportError:
        from wake import set_config
    r = set_config(payload.get("keyword", ""), float(payload.get("threshold", 0)),
                   int(payload.get("cooldown_s", 0)))
    await hub.push()
    return r

@app.post("/voice/stream/start")
async def stream_start(_=Depends(need_auth)):
    try:
        from app.wake import stream_start as _ss
    except ImportError:
        from wake import stream_start as _ss
    return {"ok": True, "stream": _ss()}

@app.post("/voice/stream/chunk")
async def stream_chunk(payload: dict, _=Depends(need_auth)):
    try:
        from app.wake import stream_chunk as _sc
    except ImportError:
        from wake import stream_chunk as _sc
    r = _sc(payload.get("stream", ""), payload.get("audio_b64", ""), int(payload.get("ms", 100)))
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("error", "bad chunk"))
    return r

@app.post("/voice/stream/finish")
async def stream_finish(payload: dict, _=Depends(need_auth)):
    try:
        from app.wake import stream_finish as _sf
    except ImportError:
        from wake import stream_finish as _sf
    r = _sf(payload.get("stream", ""))
    if not r.get("ok"):
        raise HTTPException(status_code=502, detail=r.get("error", "transcribe failed"))
    return r

# ---- v0.5: spend optimizer ----
@app.get("/usage/optimize")
def usage_optimize(days: int = 30, _=Depends(need_auth)):
    try:
        from app.optimizer import report
    except ImportError:
        from optimizer import report
    return report(days)

# ---- v0.5: public share links (capability URLs, revocable) ----
@app.post("/share/links")
async def share_link_create(payload: dict, _=Depends(need_auth)):
    try:
        from app.share import create_link
    except ImportError:
        from share import create_link
    r = create_link(payload.get("kind", "goal"), int(payload.get("ref", 0)),
                    float(payload.get("ttl_hours", 72)))
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("error", "bad link"))
    await hub.push()
    return r

@app.get("/share/links")
def share_link_list(_=Depends(need_auth)):
    try:
        from app.share import list_links
    except ImportError:
        from share import list_links
    return {"links": list_links()}

@app.post("/share/links/revoke")
async def share_link_revoke(payload: dict, _=Depends(need_auth)):
    try:
        from app.share import revoke_link
    except ImportError:
        from share import revoke_link
    r = revoke_link(payload.get("token", ""))
    await hub.push()
    return r

@app.get("/s/{token}")
def share_view(token: str):
    """Public read-only page. No auth — the unguessable token IS the auth."""
    from fastapi.responses import HTMLResponse as _HTML
    try:
        from app.share import resolve_link, render_goal_page
    except ImportError:
        from share import resolve_link, render_goal_page
    link = resolve_link(token)
    if not link:
        return _HTML("<h1>Link expired, revoked, or invalid</h1>", status_code=404)
    if link["kind"] == "goal":
        return _HTML(render_goal_page(link["ref"]))
    return _HTML("<h1>Unknown share kind</h1>", status_code=404)

# ---- v0.5: research digests ----
@app.post("/digests/topics")
async def digest_add(payload: dict, _=Depends(need_auth)):
    try:
        from app.digest import add_topic
    except ImportError:
        from digest import add_topic
    r = add_topic(payload.get("topic", ""))
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("error", "bad topic"))
    await hub.push()
    return r

@app.get("/digests/topics")
def digest_topics(_=Depends(need_auth)):
    try:
        from app.digest import list_topics
    except ImportError:
        from digest import list_topics
    return {"topics": list_topics()}

@app.post("/digests/topics/{tid}/enable")
async def digest_enable(tid: int, payload: dict, _=Depends(need_auth)):
    try:
        from app.digest import set_active
    except ImportError:
        from digest import set_active
    r = set_active(tid, bool(payload.get("active", True)))
    await hub.push()
    return r

@app.delete("/digests/topics/{tid}")
async def digest_delete(tid: int, _=Depends(need_auth)):
    try:
        from app.digest import remove_topic
    except ImportError:
        from digest import remove_topic
    r = remove_topic(tid)
    await hub.push()
    return r

@app.get("/digests")
def digest_latest(limit: int = 10, _=Depends(need_auth)):
    try:
        from app.digest import latest
    except ImportError:
        from digest import latest
    return {"digests": latest(limit)}

# ---- v0.6: plugin sandbox runtime ----
@app.post("/sandbox/run")
async def sandbox_run(payload: dict, _=Depends(need_auth)):
    try:
        from app.runtime import run
    except ImportError:
        from runtime import run
    r = run(payload.get("skill", ""), payload.get("action", ""), payload.get("args", {}))
    await hub.push()
    return r

@app.get("/sandbox/audit")
def sandbox_audit(skill: str = "", limit: int = 30, _=Depends(need_auth)):
    try:
        from app.runtime import audit
    except ImportError:
        from runtime import audit
    return {"audit": audit(skill, limit)}

@app.post("/sandbox/kill")
async def sandbox_kill(payload: dict, _=Depends(need_auth)):
    try:
        from app.runtime import kill, unkill
    except ImportError:
        from runtime import kill, unkill
    r = unkill(payload.get("skill", "")) if payload.get("revive") else kill(payload.get("skill", ""))
    await hub.push()
    return r

# ---- v0.6: cross-device handoff ----
@app.post("/handoff/create")
async def handoff_create(payload: dict, _=Depends(need_auth)):
    try:
        from app.handoff import create
    except ImportError:
        from handoff import create
    r = create(int(payload.get("gid", 0)), payload.get("from_device", "unknown"),
               payload.get("to_device", ""), payload.get("sealed"))
    if not r.get("ok"):
        raise HTTPException(status_code=404, detail=r.get("error", "no such goal"))
    await hub.push()
    return r

@app.get("/handoff/pending")
def handoff_pending(device: str, _=Depends(need_auth)):
    try:
        from app.handoff import pending
    except ImportError:
        from handoff import pending
    return {"pending": pending(device)}

@app.post("/handoff/{hid}/accept")
async def handoff_accept(hid: int, payload: dict, _=Depends(need_auth)):
    try:
        from app.handoff import accept
    except ImportError:
        from handoff import accept
    r = accept(hid, payload.get("device", "unknown"))
    if not r.get("ok"):
        raise HTTPException(status_code=409, detail=r.get("error", "cannot accept"))
    await hub.push()
    return r

# ---- v0.6: SLM weights drop-in ----
@app.post("/slm/fetch")
async def slm_fetch(payload: dict, _=Depends(need_auth)):
    import asyncio as _aio
    try:
        from app.slm import fetch_weights
    except ImportError:
        from slm import fetch_weights
    r = await _aio.to_thread(fetch_weights, payload.get("url", ""))
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("error", "fetch failed"))
    await hub.push()
    return r

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

@app.get("/wardrobe/plan-week")
def w_plan_week(_=Depends(need_auth)):
    return _w().plan_week()

@app.post("/wardrobe/plan-occasion")
async def w_plan_occasion(payload: dict, _=Depends(need_auth)):
    return _w().plan_occasion(payload.get("occasion", ""), payload.get("day", ""))

@app.post("/wardrobe/pack")
async def w_pack(payload: dict, _=Depends(need_auth)):
    r = _w().pack_trip(int(payload.get("days", 2)), payload.get("dest", ""))
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("reply", "pack failed"))
    return r

@app.post("/wardrobe/laundry-done")
async def w_laundry(_=Depends(need_auth)):
    r = _w().laundry_done()
    await hub.push()
    return r

@app.post("/wardrobe/intake")
async def w_intake(payload: dict, _=Depends(need_auth)):
    """Photo intake: {image_b64} -> vision describes -> wardrobe item."""
    if not payload.get("image_b64"):
        raise HTTPException(status_code=400, detail="image_b64 required")
    r = _w().intake_image(payload["image_b64"])
    if not r.get("ok"):
        raise HTTPException(status_code=502, detail=r.get("reply", "vision failed"))
    await hub.push()
    return r

# ---- bills scale-up: settle-up, recurring, UPI, team-house, receipt scan ----
@app.get("/bills/settle-up/{gid}")
def bills_settle_up(gid: int, _=Depends(need_auth)):
    try:
        from app.bills import settle_up
    except ImportError:
        from bills import settle_up
    return settle_up(gid)

@app.post("/bills/upi")
async def bills_upi(payload: dict, _=Depends(need_auth)):
    try:
        from app.bills import set_upi
    except ImportError:
        from bills import set_upi
    r = set_upi(int(payload.get("gid", 0)), payload.get("name", "Me"), payload.get("upi", ""))
    await hub.push()
    return r

@app.post("/bills/recurring")
async def bills_rec_add(payload: dict, _=Depends(need_auth)):
    try:
        from app.bills import add_recurring
    except ImportError:
        from bills import add_recurring
    r = add_recurring(int(payload.get("gid", 0)), payload.get("title", ""), float(payload.get("amount", 0)),
                      payload.get("paid_by", "Me"), payload.get("splits") or {}, int(payload.get("day", 1)))
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("error", "bad recurring"))
    await hub.push()
    return r

@app.get("/bills/recurring")
def bills_rec_list(gid: int = 0, _=Depends(need_auth)):
    try:
        from app.bills import list_recurring
    except ImportError:
        from bills import list_recurring
    return {"recurring": list_recurring(gid)}

@app.post("/bills/link-team")
async def bills_link_team(payload: dict, _=Depends(need_auth)):
    try:
        from app.bills import link_team
    except ImportError:
        from bills import link_team
    r = link_team(int(payload.get("gid", 0)), int(payload.get("team", 0)))
    await hub.push()
    return r

@app.get("/bills/house-ledger/{gid}")
def bills_house(gid: int, ym: str = "", _=Depends(need_auth)):
    try:
        from app.bills import house_ledger
    except ImportError:
        from bills import house_ledger
    r = house_ledger(gid, ym)
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("error", "bad ledger"))
    return r

@app.post("/bills/receipt")
async def bills_receipt(payload: dict, _=Depends(need_auth)):
    """Receipt scan: {image_b64} -> draft expense. Confirm via POST /bills/expenses."""
    if not payload.get("image_b64"):
        raise HTTPException(status_code=400, detail="image_b64 required")
    try:
        from app.bills import parse_receipt
    except ImportError:
        from bills import parse_receipt
    r = parse_receipt(payload["image_b64"])
    if not r.get("ok"):
        raise HTTPException(status_code=502, detail=r.get("error", "scan failed"))
    return r

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
    try:
        cap = _fillq().captcha_count()
    except Exception:
        cap = 0
    n["captcha"] = cap
    n["unread"] = n.get("unread", 0) + cap
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
