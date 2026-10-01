"""Social connectors — our own design. Post/read across platforms with capability
manifests, idempotent publishes, and per-destination outcomes.

Platforms: mock (contract tests, no creds), x, linkedin (direct adapters,
tokens in vault). Manifests declare support BEFORE attempting; publishes carry
idempotency keys so retries never double-post; every outcome recorded.
"""
import json
import os
import time
import uuid as _uuid

try:
    from app.db import connect as _hardb
    from app.paths import data as _pdata
except ImportError:
    from db import connect as _hardb
    from paths import data as _pdata

DB = _pdata("osokai.db")

# platform -> capabilities (checked before attempting, like a manifest)
MANIFESTS = {
    "mock": {"post_text": True, "post_media": False, "read": True, "dm": False,
             "max_chars": 280, "needs": []},
    "x": {"post_text": True, "post_media": True, "read": True, "dm": True,
          "max_chars": 280, "needs": ["X_BEARER_TOKEN"]},
    "linkedin": {"post_text": True, "post_media": True, "read": False, "dm": False,
                 "max_chars": 3000, "needs": ["LINKEDIN_ACCESS_TOKEN"]},
}

PROVIDERS = {
    "x": {"name": "X", "needs_env": "X_BEARER_TOKEN"},
    "linkedin": {"name": "LinkedIn", "needs_env": "LINKEDIN_ACCESS_TOKEN"},
}


def _db():
    db = _hardb(os.path.normpath(DB))
    db.execute("""CREATE TABLE IF NOT EXISTS social_posts(
        id INTEGER PRIMARY KEY, platform TEXT, text TEXT, status TEXT,
        idemp TEXT UNIQUE, outcome TEXT DEFAULT '{}', ts REAL)""")
    return db


def manifest(platform: str):
    return MANIFESTS.get((platform or "").lower())


def _token(platform: str) -> str:
    """Connector store first (pasted via UI, encrypted at rest), env fallback."""
    try:
        try:
            from app.connectors import _load
            from app.vault import decrypt
        except ImportError:
            from connectors import _load
            from vault import decrypt
        entry = (_load() or {}).get(platform, {})
        if entry.get("enc"):
            try:
                tok = decrypt(entry["enc"])
                if tok:
                    return tok
            except Exception:
                pass
    except Exception:
        pass
    need = PROVIDERS.get(platform, {}).get("needs_env", "")
    return os.getenv(need, "") if need else "mock"


def draft(platform: str, text: str) -> dict:
    """Stage a post (no side effects). Returns draft id for the approval card."""
    man = manifest(platform)
    if not man:
        return {"ok": False, "error": f"unsupported platform '{platform}'"}
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "empty post"}
    if len(text) > man["max_chars"]:
        return {"ok": False, "error": f"too long ({len(text)} > {man['max_chars']} chars)"}
    db = _db()
    key = f"draft-{_uuid.uuid4().hex[:12]}"
    cur = db.execute("INSERT INTO social_posts(platform, text, status, idemp, ts) VALUES(?,?,?,?,?)",
                     (platform, text[:2000], "draft", key, time.time()))
    db.commit()
    return {"ok": True, "id": cur.lastrowid, "idemp": key}


def publish(platform: str, text: str, idemp: str = "") -> dict:
    """Publish with idempotency: same key replays the stored outcome, never re-posts."""
    man = manifest(platform)
    if not man:
        return {"ok": False, "error": f"unsupported platform '{platform}'"}
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "empty post"}
    if len(text) > man["max_chars"]:
        return {"ok": False, "error": f"too long ({len(text)} > {man['max_chars']} chars)"}
    key = (idemp or f"pub-{_uuid.uuid4().hex[:12]}")[:128]
    db = _db()
    dup = db.execute("SELECT id, status, outcome FROM social_posts WHERE idemp=?", (key,)).fetchone()
    if dup:
        import json as _j
        return {"ok": True, "id": dup[0], "replay": True, "status": dup[1],
                "outcome": _j.loads(dup[2] or "{}")}
    if platform == "mock":
        outcome = {"state": "complete", "post_id": f"mock-{key[:8]}"}
    else:
        tok = _token(platform)
        if not tok:
            return {"ok": False, "error": f"no token: set {PROVIDERS[platform]['needs_env']}"}
        outcome = _direct_post(platform, tok, text)
        if not outcome.get("ok"):
            return outcome
    cur = db.execute("INSERT INTO social_posts(platform, text, status, idemp, outcome, ts) VALUES(?,?,?,?,?,?)",
                     (platform, text[:2000], outcome.get("state", "complete"),
                      key, json.dumps(outcome)[:2000], time.time()))
    db.commit()
    try:
        from app.context.normalizers import _emit
    except ImportError:
        try:
            from context.normalizers import _emit
        except ImportError:
            _emit = lambda *a, **k: None
    try:
        _emit("social.published", {"id": cur.lastrowid, "platform": platform}, "social")
    except Exception:
        pass
    return {"ok": True, "id": cur.lastrowid, "status": outcome.get("state", "complete"), "outcome": outcome}


def _direct_post(platform: str, token: str, text: str) -> dict:
    import httpx as _hx
    try:
        if platform == "x":
            r = _hx.post("https://api.x.com/2/tweets",
                         headers={"Authorization": f"Bearer {token}"},
                         json={"text": text}, timeout=30)
            d = r.json() if r.status_code in (200, 201) else {}
            if r.status_code not in (200, 201) or not d.get("data", {}).get("id"):
                return {"ok": False, "error": f"x rejected: {r.status_code} {r.text[:150]}"}
            return {"ok": True, "state": "complete", "post_id": d["data"]["id"]}
        if platform == "linkedin":
            me = _hx.get("https://api.linkedin.com/v2/userinfo",
                          headers={"Authorization": f"Bearer {token}"}, timeout=20).json()
            sub = me.get("sub", "")
            if not sub:
                return {"ok": False, "error": "linkedin: bad token/userinfo"}
            r = _hx.post("https://api.linkedin.com/v2/ugcPosts",
                         headers={"Authorization": f"Bearer {token}", "X-Restli-Protocol-Version": "2.0.0"},
                         json={"author": f"urn:li:person:{sub}",
                               "lifecycleState": "PUBLISHED",
                               "specificContent": {"com.linkedin.ugc.ShareContent": {
                                   "shareCommentary": {"text": text},
                                   "shareMediaCategory": "NONE"}},
                               "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}},
                         timeout=30)
            if r.status_code not in (200, 201):
                return {"ok": False, "error": f"linkedin rejected: {r.status_code} {r.text[:150]}"}
            return {"ok": True, "state": "complete", "post_id": r.headers.get("x-restli-id", "")}
    except Exception as e:
        return {"ok": False, "error": f"{platform} post failed: {e}"[:200]}
    return {"ok": False, "error": "unsupported platform"}


def status(post_id: int = 0, limit: int = 20):
    db = _db()
    q = "SELECT id, platform, text, status, idemp, outcome, ts FROM social_posts"
    args: tuple = ()
    if post_id:
        q += " WHERE id=?"
        args = (post_id,)
    q += " ORDER BY id DESC LIMIT ?"
    rows = db.execute(q, args + (max(1, min(50, limit)),)).fetchall()
    out = []
    for r in rows:
        try:
            oc = json.loads(r[5] or "{}")
        except Exception:
            oc = {}
        out.append({"id": r[0], "platform": r[1], "text": (r[2] or "")[:200],
                    "status": r[3], "idemp": r[4], "outcome": oc, "ts": r[6]})
    return out
