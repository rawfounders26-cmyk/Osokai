"""Real OAuth — Google (Gmail), Microsoft (Outlook), Slack.
Flow: GET /connectors/{id}/login -> authorize URL (paste CLIENT_ID/SECRET in .env first)
  -> user approves -> GET /connectors/callback?provider=&code= -> tokens encrypted in vault.
Without credentials the endpoints say exactly what's missing (never fake)."""
import os, urllib.parse
import httpx

REDIRECT = os.getenv("OAUTH_REDIRECT", "http://localhost:8765/connectors/callback")

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

def authorize_url(provider: str) -> str:
    if provider == "gmail":
        cid, _ = _google_cfg()
        q = urllib.parse.urlencode({
            "client_id": cid, "redirect_uri": REDIRECT, "response_type": "code",
            "scope": "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send",
            "access_type": "offline", "prompt": "consent"})
        return "https://accounts.google.com/o/oauth2/v2/auth?" + q
    if provider == "outlook":
        cid, _ = _ms_cfg()
        q = urllib.parse.urlencode({
            "client_id": cid, "redirect_uri": REDIRECT, "response_type": "code",
            "scope": "Mail.Read Mail.Send offline_access", "response_mode": "query"})
        return "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?" + q
    if provider == "slack":
        cid, _ = _slack_cfg()
        q = urllib.parse.urlencode({"client_id": cid, "redirect_uri": REDIRECT,
                                    "scope": "channels:read,chat:write", "response_type": "code"})
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
