"""Real OAuth — Google (Gmail), Microsoft (Outlook), Slack.
Flow: GET /connectors/{id}/auth-url -> authorize URL with single-use state
  -> user approves -> GET /connectors/callback?code=&state= -> state binds
  provider+device (login-CSRF safe) -> tokens encrypted in vault.
Without credentials the endpoints say exactly what's missing (never fake)."""
import os
import secrets
import time
import urllib.parse
import httpx

REDIRECT = os.getenv("OAUTH_REDIRECT", "http://localhost:8765/connectors/callback")
STATE_TTL = 600

def _google_cfg():
    cid, sec = os.getenv("GOOGLE_CLIENT_ID", ""), os.getenv("GOOGLE_CLIENT_SECRET", "")
    if not cid or not sec:
        raise RuntimeError("Add GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET in backend/.env (Google Cloud Console → OAuth web client, redirect: " + REDIRECT + ")")
    return cid, sec

def _ms_cfg():
    cid, sec = os.getenv("MS_CLIENT_ID", ""), os.getenv("MS_CLIENT_SECRET", "")
    if not cid or not sec:
        raise RuntimeError("Add MS_CLIENT_ID + MS_CLIENT_SECRET in backend/.env (Azure → app registration, redirect: " + REDIRECT + ")")
    return cid, sec

def _slack_cfg():
    cid, sec = os.getenv("SLACK_CLIENT_ID", ""), os.getenv("SLACK_CLIENT_SECRET", "")
    if not cid or not sec:
        raise RuntimeError("Add SLACK_CLIENT_ID + SLACK_CLIENT_SECRET in backend/.env (api.slack.com/apps → OAuth, redirect: " + REDIRECT + ")")
    return cid, sec

def _states_db():
    import sqlite3
    try:
        from app.paths import data as _pdata
    except ImportError:
        from paths import data as _pdata
    try:
        from app.db import connect as _hardb
    except ImportError:
        from db import connect as _hardb
    db = _hardb(os.path.normpath(_pdata("osokai.db")))
    db.execute("CREATE TABLE IF NOT EXISTS oauth_states(state TEXT PRIMARY KEY, provider TEXT, device TEXT, exp REAL)")
    return db


def new_state(provider: str, device: str = "unknown") -> str:
    """Single-use, 10-min login-CSRF token binding provider + initiating device."""
    if provider not in ("gmail", "outlook", "slack"):
        raise RuntimeError("OAuth not supported for " + provider)
    st = secrets.token_urlsafe(24)
    db = _states_db()
    db.execute("DELETE FROM oauth_states WHERE exp<?", (time.time(),))
    db.execute("INSERT INTO oauth_states(state, provider, device, exp) VALUES(?,?,?,?)",
               (st, provider, (device or "unknown")[:80], time.time() + STATE_TTL))
    db.commit()
    return st


def consume_state(state: str):
    """Returns {provider, device} once, then burns. None if bad/expired/used."""
    db = _states_db()
    r = db.execute("SELECT provider, device, exp FROM oauth_states WHERE state=?", (state or "",)).fetchone()
    if not r:
        return None
    db.execute("DELETE FROM oauth_states WHERE state=?", (state,))
    db.commit()
    if r[2] < time.time():
        return None
    return {"provider": r[0], "device": r[1]}


def authorize_url(provider: str, state: str = "") -> str:
    if provider == "gmail":
        cid, _ = _google_cfg()
        q = urllib.parse.urlencode({
            "client_id": cid, "redirect_uri": REDIRECT, "response_type": "code",
            "scope": "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send",
            "access_type": "offline", "prompt": "consent", "state": state})
        return "https://accounts.google.com/o/oauth2/v2/auth?" + q
    if provider == "outlook":
        cid, _ = _ms_cfg()
        q = urllib.parse.urlencode({
            "client_id": cid, "redirect_uri": REDIRECT, "response_type": "code",
            "scope": "Mail.Read Mail.Send offline_access", "response_mode": "query", "state": state})
        return "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?" + q
    if provider == "slack":
        cid, _ = _slack_cfg()
        q = urllib.parse.urlencode({"client_id": cid, "redirect_uri": REDIRECT,
                                    "scope": "channels:read,chat:write", "response_type": "code", "state": state})
        return "https://slack.com/oauth/v2/authorize?" + q
    raise RuntimeError("OAuth not supported for " + provider + " (use token pairing)")

def exchange(provider: str, code: str) -> dict:
    if provider == "gmail":
        cid, sec = _google_cfg()
        r = httpx.post("https://oauth2.googleapis.com/token",
                       data={"client_id": cid, "client_secret": sec, "code": code,
                             "grant_type": "authorization_code", "redirect_uri": REDIRECT}, timeout=30)
        r.raise_for_status()
        return r.json()
    if provider == "outlook":
        cid, sec = _ms_cfg()
        r = httpx.post("https://login.microsoftonline.com/common/oauth2/v2.0/token",
                       data={"client_id": cid, "client_secret": sec, "code": code,
                             "grant_type": "authorization_code", "redirect_uri": REDIRECT}, timeout=30)
        r.raise_for_status()
        return r.json()
    if provider == "slack":
        cid, sec = _slack_cfg()
        r = httpx.post("https://slack.com/api/oauth.v2.access",
                       data={"client_id": cid, "client_secret": sec, "code": code,
                             "redirect_uri": REDIRECT}, timeout=30)
        d = r.json()
        if not d.get("ok"):
            raise RuntimeError("slack: " + d.get("error", "oauth failed"))
        return d
    raise RuntimeError("OAuth not supported for " + provider)

def _refresh_google(refresh_token: str) -> dict:
    cid, sec = _google_cfg()
    r = httpx.post("https://oauth2.googleapis.com/token",
                   data={"client_id": cid, "client_secret": sec, "refresh_token": refresh_token,
                         "grant_type": "refresh_token"}, timeout=30)
    r.raise_for_status()
    return r.json()

def gmail_unread(access_token: str) -> int:
    r = httpx.get("https://gmail.googleapis.com/gmail/v1/users/me/labels/INBOX",
                  headers={"Authorization": f"Bearer {access_token}"}, timeout=20)
    if r.status_code == 401:
        raise PermissionError("gmail token expired")
    r.raise_for_status()
    return int(r.json().get("messagesUnread", 0))

def outlook_unread(access_token: str) -> int:
    r = httpx.get("https://graph.microsoft.com/v1.0/me/mailFolders/inbox?$select=unreadItemCount",
                  headers={"Authorization": f"Bearer {access_token}"}, timeout=20)
    if r.status_code == 401:
        raise PermissionError("outlook token expired")
    r.raise_for_status()
    return int(r.json().get("unreadItemCount", 0))
