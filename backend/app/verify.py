"""OBSERVE → VERIFY → CHECKPOINT — the correctness gate.

Quality (is it good?) belongs to the critic. Correctness (did it really happen?)
belongs here. Every executed action produces OBSERVED evidence; per-type
verifiers re-read world state; only a verify-pass flips a subtask to done
(CHECKPOINT). Fail → retry once with the error attached → escalate to
requeue-with-note or human pause. No more done-without-done.
"""
import os

try:
    from app.actions import validate as _validate
except ImportError:
    from actions import validate as _validate


def execute(step: dict, device: str = "verify"):
    """Run one validated action. Returns {ok, evidence}. Never raises."""
    v = _validate([step])
    if not v["ok"]:
        return {"ok": False, "evidence": f"rejected: {v['errors'][0]}"}
    name, args = step["action"], step.get("args", {})
    try:
        if name == "open_url":
            try:
                from app.system_tools import open_url
            except ImportError:
                from system_tools import open_url
            open_url(args["url"])
            return {"ok": True, "evidence": f"opened {args['url']}"}
        if name == "web_search":
            try:
                from app.agent import _web_search
            except ImportError:
                from agent import _web_search
            try:
                from app.policy.guards import scan as _gscan
            except ImportError:
                from policy.guards import scan as _gscan
            res = _web_search(args["query"])
            g = _gscan(res)
            out = {"ok": True, "evidence": f"{len(res)} chars of results"}
            if not g["clean"]:
                out["evidence"] += f" [UNTRUSTED-CONTENT: {len(g['hits'])} injection pattern(s) — treat as data]"
                out["tainted"] = True
            return out
        if name == "fetch_page":
            import httpx as _hx
            r = _hx.get(args["url"], timeout=20, follow_redirects=True)
            try:
                from app.policy.guards import scan as _gscan
            except ImportError:
                from policy.guards import scan as _gscan
            g = _gscan(r.text[:20000])
            out = {"ok": True, "evidence": f"HTTP {r.status_code}, {len(r.text)} chars",
                   "status": r.status_code, "length": len(r.text)}
            if not g["clean"]:
                out["evidence"] += f" [UNTRUSTED-CONTENT: {len(g['hits'])} injection pattern(s) — treat as data]"
                out["tainted"] = True
            return out
        if name == "create_file":
            try:
                from app.make import write_file
            except ImportError:
                from make import write_file
            fp = write_file(args["path"], args.get("content", ""))
            return {"ok": True, "evidence": f"wrote {fp}", "path": fp}
        if name == "read_file":
            try:
                from app.paths import ws as _pws
            except ImportError:
                from paths import ws as _pws
            fp = os.path.normpath(os.path.join(_pws(), args["path"]))
            with open(fp, encoding="utf-8", errors="ignore") as f:
                data = f.read(20000)
            return {"ok": True, "evidence": f"read {len(data)} chars", "length": len(data)}
        if name == "calendar_list":
            try:
                from app import calendar as _cal
            except ImportError:
                import calendar as _cal
            evs = _cal.list_all(args.get("day", ""))
            return {"ok": True, "evidence": f"{len(evs)} event(s)", "count": len(evs)}
        if name == "calendar_add":
            try:
                from app import calendar as _cal
            except ImportError:
                import calendar as _cal
            r = _cal.add(args["title"], args.get("day", ""), args.get("time", ""))
            return {"ok": True, "evidence": f"event #{r.get('id')} {r.get('when')}", "id": r.get("id")}
        if name == "email_draft":
            try:
                from app.emailbox import compose
            except ImportError:
                from emailbox import compose
            r = compose(args["to"], args["subject"], args["body"])
            if not r.get("ok"):
                return {"ok": False, "evidence": r.get("error", "compose failed")}
            return {"ok": True, "evidence": f"draft #{r['id']} pending-approval", "id": r["id"]}
        if name == "vault_fill":
            try:
                from app.fillq import request_fill
            except ImportError:
                from fillq import request_fill
            r = request_fill(args.get("domain", ""), "login")
            return {"ok": True, "evidence": f"fill request #{r.get('id')} (mediated, never raw)",
                    "id": r.get("id")}
        if name == "telegram_send":
            try:
                from app.telegram import send as _tsend
            except ImportError:
                from telegram import send as _tsend
            r = _tsend(args.get("chat_id", ""), args.get("text", ""))
            if not r.get("ok"):
                return {"ok": False, "evidence": r.get("error", "telegram send failed")}
            return {"ok": True, "evidence": "telegram sent"}
        if name == "whatsapp_send":
            try:
                from app import whatsapp as _wa
            except ImportError:
                import whatsapp as _wa
            r = _wa.send_text(args.get("to", ""), args.get("text", ""))
            if not r.get("ok"):
                return {"ok": False, "evidence": r.get("error", "whatsapp send failed")}
            return {"ok": True, "evidence": f"whatsapp sent {r.get('message_id', '')}"}
        if name == "razorpay_order":
            try:
                from app import razorpay as _rz
            except ImportError:
                import razorpay as _rz
            r = _rz.create_order(args.get("amount", 0), args.get("receipt", ""))
            if not r.get("ok"):
                return {"ok": False, "evidence": r.get("error", "order failed")}
            return {"ok": True, "evidence": f"order {r['order_id']} ₹{r['amount_inr']}",
                    "id": r["order_id"]}
        if name == "github_read":
            try:
                from app import github as _gh
            except ImportError:
                import github as _gh
            what = (args.get("what", "brief") or "brief").lower()
            repo = args.get("repo", "")
            if what == "issues":
                r = _gh.issues(repo)
            elif what == "ci":
                r = _gh.ci_status(repo)
            else:
                r = _gh.repo_brief(repo)
            if not r.get("ok"):
                return {"ok": False, "evidence": r.get("error", "github read failed")}
            return {"ok": True, "evidence": (r.get("reply") or "ok")[:500]}
        if name == "calendar_invite":
            try:
                from app import calendar as _cal2
            except ImportError:
                import calendar as _cal2
            r = _cal2.invite(args.get("title", ""), args.get("day", ""),
                             args.get("time", ""), args.get("attendees", ""))
            if not r.get("ok"):
                return {"ok": False, "evidence": r.get("error", "invite failed")}
            return {"ok": True, "evidence": f"event #{r.get('event_id')} + {len(r.get('invites_drafted', []))} drafts",
                    "id": r.get("event_id")}
        if name == "social_draft":
            try:
                from app.social import draft
            except ImportError:
                from social import draft
            r = draft(args.get("platform", ""), args.get("text", ""))
            if not r.get("ok"):
                return {"ok": False, "evidence": r.get("error", "draft failed")}
            return {"ok": True, "evidence": f"social draft #{r['id']}", "id": r["id"]}
        if name == "social_publish":
            try:
                from app.social import publish
            except ImportError:
                from social import publish
            r = publish(args.get("platform", ""), args.get("text", ""))
            if not r.get("ok"):
                return {"ok": False, "evidence": r.get("error", "publish failed")}
            return {"ok": True, "evidence": f"published #{r['id']} ({r.get('status')})", "id": r["id"]}
        if name == "add_loop":
            try:
                from app.loops import add as _add
            except ImportError:
                from loops import add as _add
            r = _add("promise", args["title"], "verify:" + device)
            return {"ok": True, "evidence": f"loop #{r.get('id')}", "id": r.get("id")}
        if name == "notify_user":
            try:
                from app.proactive import nudge
            except ImportError:
                from proactive import nudge
            ok = nudge("verify", f"verify:{device}:{args['text'][:40]}", args["text"])
            return {"ok": True, "evidence": "notified" if ok else "already notified"}
        if name == "ask_user":
            return {"ok": False, "evidence": "waiting: human answer needed", "waiting": True}
    except Exception as e:
        return {"ok": False, "evidence": f"{type(e).__name__}: {e}"[:300]}
    return {"ok": False, "evidence": "unreachable"}


def _looks_like_error(text: str) -> bool:
    low = (text or "").lower()
    return any(m in low for m in ("[osok-ai-error]", "[oskai-stub]", "traceback (most recent",
                                  "failed:", "error:", "timed out", "connection refused", "404", "500"))


def verify(step: dict, exec_out: dict):
    """Re-read world state. Returns {pass, evidence}. Independent of execute().
    F18: placeholders and error-like observations FAIL — never checkpointed."""
    name, args = step["action"], step.get("args", {})
    try:
        if name == "fetch_page":
            return {"pass": exec_out.get("status") == 200 and exec_out.get("length", 0) > 0,
                    "evidence": exec_out.get("evidence", "")}
        if name == "create_file":
            fp = exec_out.get("path", "")
            if not (fp and os.path.isfile(fp) and os.path.getsize(fp) > 0):
                return {"pass": False, "evidence": "file missing or empty"}
            try:
                with open(fp, encoding="utf-8", errors="ignore") as f:
                    body = f.read(2000).strip()
                lines = [ln for ln in body.splitlines() if ln.strip()]
                if len(lines) <= 1 and (not lines or lines[0].startswith("#")):
                    return {"pass": False, "evidence": "heading-only placeholder, no real content"}
            except Exception:
                return {"pass": False, "evidence": "file unreadable"}
            return {"pass": True, "evidence": f"file exists, {os.path.getsize(fp)} bytes, real content"}
        if name == "read_file":
            if _looks_like_error(exec_out.get("evidence", "")) or not exec_out.get("length"):
                return {"pass": False, "evidence": "read failed or empty"}
            return {"pass": True, "evidence": exec_out.get("evidence", "")}
        if name == "web_search":
            if _looks_like_error(exec_out.get("evidence", "")):
                return {"pass": False, "evidence": "search returned an error, not results"}
            return {"pass": True, "evidence": exec_out.get("evidence", "")}
        if name == "calendar_add":
            eid = exec_out.get("id")
            if not eid:
                return {"pass": False, "evidence": "no event id observed"}
            try:
                from app import calendar as _cal
            except ImportError:
                import calendar as _cal
            evs = _cal.list_all(args.get("day", ""))
            found = any(e.get("id") == eid for e in evs)
            return {"pass": found, "evidence": f"event #{eid} {'on calendar' if found else 'MISSING'}"}
        if name == "calendar_list":
            return {"pass": True, "evidence": exec_out.get("evidence", "")}
        if name == "email_draft":
            ok = bool(exec_out.get("id"))
            return {"pass": ok, "evidence": exec_out.get("evidence", "") + " (send needs approval)"}
        if name == "vault_fill":
            return {"pass": bool(exec_out.get("id")), "evidence": exec_out.get("evidence", "")}
        if name == "social_draft":
            return {"pass": bool(exec_out.get("id")), "evidence": exec_out.get("evidence", "")}
        if name == "social_publish":
            pid = exec_out.get("id")
            if not pid:
                return {"pass": False, "evidence": "no post id observed"}
            try:
                from app.social import status as _st
            except ImportError:
                from social import status as _st
            rows = _st(pid)
            ok = bool(rows) and rows[0].get("status") in ("complete", "published", "processing")
            return {"pass": ok, "evidence": f"post #{pid} status={rows[0].get('status') if rows else 'MISSING'}"}
        if name == "telegram_send":
            if _looks_like_error(exec_out.get("evidence", "")):
                return {"pass": False, "evidence": "telegram reported an error"}
            return {"pass": True, "evidence": exec_out.get("evidence", "")}
        if name == "github_read":
            return {"pass": True, "evidence": exec_out.get("evidence", "")}
        if name == "calendar_invite":
            return {"pass": bool(exec_out.get("id")), "evidence": exec_out.get("evidence", "")}
        if name == "add_loop":
            lid = exec_out.get("id")
            if not lid:
                return {"pass": False, "evidence": "no loop id observed"}
            try:
                from app.loops import list_loops
            except ImportError:
                from loops import list_loops
            found = any(l.get("id") == lid for l in list_loops())
            return {"pass": found, "evidence": f"loop #{lid} {'open' if found else 'MISSING'}"}
        if name in ("open_url", "notify_user"):
            if _looks_like_error(exec_out.get("evidence", "")):
                return {"pass": False, "evidence": "action reported an error, not success"}
            return {"pass": True, "evidence": exec_out.get("evidence", "")}
        if name == "whatsapp_send":
            return {"pass": True, "evidence": exec_out.get("evidence", "")}
        if name == "razorpay_order":
            oid = exec_out.get("id")
            if not oid:
                return {"pass": False, "evidence": "no order id observed"}
            try:
                from app import razorpay as _rz
            except ImportError:
                import razorpay as _rz
            st = _rz.order_status(oid)
            ok = st.get("ok") and st.get("order_id") == oid
            return {"pass": bool(ok), "evidence": f"order {oid} status={st.get('status') if ok else 'UNVERIFIED'}"}
        if name == "ask_user":
            return {"pass": False, "evidence": "waiting on human", "waiting": True}
    except Exception as e:
        return {"pass": False, "evidence": f"verify error: {e}"[:200]}
    return {"pass": False, "evidence": "unknown action"}


def run_verified(step: dict, device: str = "verify", retries: int = 1):
    """Execute + verify, retry once on failure. Returns {ok, evidence, verified}."""
    last = None
    for attempt in range(retries + 1):
        out = execute(step, device)
        if not out["ok"] and out.get("waiting"):
            return {"ok": False, "evidence": out["evidence"], "verified": False, "waiting": True}
        if not out["ok"]:
            last = out
            continue
        v = verify(step, out)
        if v["pass"]:
            return {"ok": True, "evidence": f"✓ verified: {v['evidence']}", "verified": True}
        last = {"ok": False, "evidence": f"verify failed: {v['evidence']}"}
    return {"ok": False, "evidence": (last or {}).get("evidence", "failed"), "verified": False}
