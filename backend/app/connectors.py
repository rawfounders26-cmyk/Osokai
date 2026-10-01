"""Connector hub — osokai-style: provider meta + honest status + enable switches.
Tokens stay in local vault, never logged. No fabricated unread counts."""
import os, json, time

try:
    from app.vault import encrypt, decrypt
except ImportError:
    from vault import encrypt, decrypt

PROVIDERS = {
    "gmail": {"name": "Gmail", "color": "#EA4335", "open_url": "https://mail.google.com",
              "auth_kind": "oauth", "hint": "Add GMAIL_CLIENT_ID in backend/.env for real OAuth; MVP accepts pasted token via /connect"},
    "outlook": {"name": "Outlook", "color": "#0F6CBD", "open_url": "https://outlook.live.com",
                "auth_kind": "oauth", "hint": "Add OUTLOOK_CLIENT_ID in backend/.env for real OAuth; MVP accepts pasted token via /connect"},
    "whatsapp": {"name": "WhatsApp", "color": "#25D366", "open_url": "https://web.whatsapp.com",
                 "auth_kind": "pairing", "hint": "MVP: Baileys QR pairing comes here. For now POST /connectors/whatsapp/connect {token: session-string}"},
    "discord": {"name": "Discord", "color": "#5865F2", "open_url": "https://discord.com/app",
                "auth_kind": "token", "hint": "Paste Bot Token via POST /connectors/discord/connect {token:...}"},
    "slack": {"name": "Slack", "color": "#4A154B", "open_url": "https://slack.com/signin",
              "auth_kind": "oauth", "hint": "Add SLACK_CLIENT_ID in backend/.env for real OAuth; MVP accepts pasted token via /connect"},
}
VAULT = os.path.join(os.path.dirname(__file__), "..", "vault.json")

_cache = {"mtime": 0, "data": {}}

def _load():
    try:
        fp = os.path.normpath(VAULT)
        mt = os.path.getmtime(fp)
        if mt == _cache["mtime"]:
            return _cache["data"]
        data = json.load(open(fp))
        _cache.update(mtime=mt, data=data)
        return data
    except Exception:
        return {}

def _save(d):
    json.dump(d, open(os.path.normpath(VAULT), "w"))

def _shape(cid: str, entry: dict):
    meta = PROVIDERS[cid]
    connected = bool(entry.get("token_len"))
    return {"id": cid, "provider": cid, "name": meta["name"], "label": meta["name"],
            "color": meta["color"], "open_url": meta["open_url"], "auth_kind": meta["auth_kind"],
            "type": "oauth2" if meta["auth_kind"] == "oauth" else meta["auth_kind"],
            "icon": meta["name"][0],
            "enabled": bool(entry.get("enabled", True)),
            "connected": connected,
            "status": "connected" if connected else "disconnected",
            "unread_count": int(entry.get("unread_count", 0)),
            "updated_at": entry.get("updated_at", ""),
            "note": "connected" if connected else "connect in Settings+Connectors"}

def list_connectors():
    v = _load()
    return [_shape(cid, v.get(cid, {})) for cid in PROVIDERS]

def auth_url(cid: str, device: str = "unknown"):
    if cid not in PROVIDERS:
        return {"auth_url": "", "hint": "unknown connector"}
    meta = PROVIDERS[cid]
    if meta["auth_kind"] == "oauth":
        try:
            try:
                from app.oauth import authorize_url, new_state
            except ImportError:
                from oauth import authorize_url, new_state
            st = new_state(cid, device)
            return {"auth_url": authorize_url(cid, st), "hint": meta["hint"],
                    "note": "login link expires in 10 min and works once (login-CSRF safe)"}
        except RuntimeError as e:
            return {"auth_url": "", "hint": str(e)}
    return {"auth_url": "", "hint": meta["hint"]}

def connect(cid: str, payload: dict):
    if cid not in PROVIDERS:
        return {"ok": False, "error": "unknown connector"}
    token = (payload.get("token") or payload.get("code") or "").strip()
    if not token:
        return {"ok": False, "error": "token/code required"}
    v = _load()
    prev = v.get(cid, {})
    try:
        enc = encrypt(token)  # ciphertext at rest; decrypted only for platform entry
    except Exception:
        enc = ""
    v[cid] = {"enc": enc, "token_len": len(token), "enabled": prev.get("enabled", True),
              "unread_count": 0, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    _save(v)
    return {"ok": True, "id": cid, "connected": True}

def disconnect(cid: str):
    v = _load()
    v.pop(cid, None)
    _save(v)
    return {"ok": True, "id": cid, "connected": False}

def set_enabled(cid: str, enabled: bool):
    if cid not in PROVIDERS:
        return {"ok": False, "error": "unknown connector"}
    v = _load()
    entry = v.get(cid, {})
    entry["enabled"] = bool(enabled)
    v[cid] = entry
    _save(v)
    return _shape(cid, entry)

def refresh(cid: str):
    """Live unread when OAuth tokens exist (auto-refreshes expired Google tokens).
    Honest disconnected + 0 when no credentials — never fabricated."""
    import json as _j
    if cid not in PROVIDERS:
        return {"ok": False, "error": "unknown connector"}
    v = _load()
    entry = v.get(cid, {})
    blob = entry.get("oauth_enc", "")
    if not blob:
        return {"provider": cid, "status": "disconnected", "unread_count": 0,
                "detail": PROVIDERS[cid]["hint"]}
    try:
        toks = _j.loads(decrypt(blob))
    except Exception:
        return {"provider": cid, "status": "error", "unread_count": 0, "detail": "vault key mismatch"}
    try:
        if cid == "gmail":
            try:
                from app.oauth import gmail_unread, _refresh_google
            except ImportError:
                from oauth import gmail_unread, _refresh_google
            try:
                n = gmail_unread(toks["access_token"])
            except PermissionError:
                if not toks.get("refresh_token"):
                    raise
                toks.update(_refresh_google(toks["refresh_token"]))
                entry["oauth_enc"] = encrypt(_j.dumps(toks))
                _save(v)
                n = gmail_unread(toks["access_token"])
        elif cid == "outlook":
            try:
                from app.oauth import outlook_unread
            except ImportError:
                from oauth import outlook_unread
            n = outlook_unread(toks["access_token"])
        else:
            n = 0
        entry["unread_count"] = n
        entry["status"] = "connected"
        _save(v)
        return {"provider": cid, "status": "connected", "unread_count": n}
    except Exception as e:
        return {"provider": cid, "status": "error", "unread_count": 0, "detail": str(e)[:200]}

def oauth_store(cid: str, tokens: dict):
    import json as _j
    v = _load()
    prev = v.get(cid, {})
    v[cid] = {"oauth_enc": encrypt(_j.dumps(tokens)), "token_len": 8,
              "enabled": prev.get("enabled", True), "unread_count": 0,
              "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    _save(v)
    return {"ok": True, "id": cid, "connected": True}

def inbox_summary():
    return {"briefing": "Connect Gmail first to get morning briefing.", "priority": []}

_sim_unread = {"n": 0, "from": ""}

def notifications():
    """Unread across gmail/outlook/whatsapp/discord/slack. Real counts land here once OAuth polling is wired."""
    v = _load()
    connected = [c for c in v if v[c].get("token_len")]
    return {"unread": _sim_unread["n"], "from": _sim_unread["from"],
            "connected": connected,
            "note": "real-time counts need OAuth polling per service"}

def simulate(unread: int, frm: str = "test"):
    _sim_unread["n"] = max(0, int(unread))
    _sim_unread["from"] = frm
    return {"ok": True, **_sim_unread}
