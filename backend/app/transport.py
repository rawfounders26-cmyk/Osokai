"""Shared connector transport — one pooled client, retries, breakers, metrics.

Every provider call flows through here instead of building throwaway httpx
clients: connection reuse (1000x fewer handshakes), exponential-backoff
retries on 429/5xx, per-provider circuit breakers (fail fast on dead
providers), and latency/cost logging into the usage dashboard.
"""
import time as _time

try:
    from app.db import connect as _hardb
    from app.paths import data as _pdata
except ImportError:
    from db import connect as _hardb
    from paths import data as _pdata

import os as _os
DB = _pdata("osokai.db")

_client = None
_breakers: dict = {}


def _db():
    db = _hardb(_os.path.normpath(DB))
    db.execute("""CREATE TABLE IF NOT EXISTS provider_health(
        provider TEXT PRIMARY KEY, calls INT DEFAULT 0, fails INT DEFAULT 0,
        ms_total INT DEFAULT 0, tripped_until REAL DEFAULT 0, updated REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS provider_cache(
        key TEXT PRIMARY KEY, body TEXT, ts REAL, ttl INT DEFAULT 300)""")
    return db


def client():
    """Process-wide pooled client. One handshake set, reused forever."""
    global _client
    if _client is None:
        import httpx as _hx
        _client = _hx.Client(timeout=30, follow_redirects=True,
                             limits=_hx.Limits(max_connections=20, max_keepalive_connections=10))
    return _client


def breaker_state(provider: str) -> dict:
    return _breakers.get(provider, {"fails": 0, "until": 0})


def _trip(provider: str, fails: int):
    _breakers[provider] = {"fails": fails, "until": _time.time() + min(600, 15 * (2 ** fails))}
    try:
        db = _db()
        db.execute("INSERT INTO provider_health(provider, fails, tripped_until, updated) VALUES(?,?,?,?) "
                   "ON CONFLICT(provider) DO UPDATE SET fails=excluded.fails, tripped_until=excluded.tripped_until, updated=excluded.updated",
                   (provider, fails, _breakers[provider]["until"], _time.time()))
        db.commit()
    except Exception:
        pass


def _record(provider: str, ok: bool, ms: int):
    st = _breakers.get(provider, {"fails": 0, "until": 0})
    if ok:
        st["fails"] = 0
        st["until"] = 0
    _breakers[provider] = st
    try:
        db = _db()
        db.execute("INSERT INTO provider_health(provider, calls, fails, ms_total, updated) VALUES(?,?,?, ?,?) "
                   "ON CONFLICT(provider) DO UPDATE SET calls=calls+?, fails=fails+?, ms_total=ms_total+?, updated=?",
                   (provider, 1, 0 if ok else 1, ms, _time.time(), 1, 0 if ok else 1, ms, _time.time()))
        db.commit()
    except Exception:
        pass
    try:
        try:
            from app.usage import log as _log
        except ImportError:
            from usage import log as _log
        _log(f"connector:{provider}", "https", "", "", ms)
    except Exception:
        pass


def call(provider: str, method: str, url: str, headers: dict = None,
         json_body: dict = None, params: dict = None, retries: int = 2) -> dict:
    """GET/POST with breaker + retries + metrics. Returns {ok, status, data, error, ms}."""
    st = breaker_state(provider)
    if st["until"] > _time.time():
        return {"ok": False, "error": f"{provider} circuit open — retry in {int(st['until'] - _time.time())}s",
                "status": 0, "ms": 0}
    t0 = _time.time()
    last = None
    for attempt in range(retries + 1):
        try:
            r = client().request(method.upper(), url, headers=headers or {},
                                 json=json_body, params=params or {})
            ms = int((_time.time() - t0) * 1000)
            ctype = r.headers.get("content-type", "")
            data = r.json() if ctype.startswith("application/json") else {"text": r.text[:5000]}
            if r.status_code in (200, 201):
                _breakers[provider] = {"fails": 0, "until": 0}
                _record(provider, True, ms)
                return {"ok": True, "status": r.status_code, "data": data, "ms": ms}
            last = {"ok": False, "status": r.status_code,
                    "error": f"{provider} {r.status_code}: {r.text[:150]}", "ms": ms}
            if r.status_code not in (429, 500, 502, 503, 504):
                _record(provider, False, ms)
                _trip(provider, st["fails"] + 1)
                return last
            _time.sleep(min(4, 0.5 * (2 ** attempt)))
        except Exception as e:
            last = {"ok": False, "status": 0, "error": f"{provider} call failed: {e}"[:200],
                    "ms": int((_time.time() - t0) * 1000)}
            _time.sleep(min(4, 0.5 * (2 ** attempt)))
    _trip(provider, st["fails"] + 1)
    _record(provider, False, last.get("ms", 0) if last else 0)
    return last or {"ok": False, "error": "no response", "status": 0, "ms": 0}


def cached_get(provider: str, key: str, url: str, headers: dict = None,
               params: dict = None, ttl: int = 300, force: bool = False):
    """Read-through cache for idempotent GETs. Cache key namespaced per provider."""
    ckey = f"{provider}:{key}"
    if not force:
        try:
            row = _db().execute("SELECT body, ts, ttl FROM provider_cache WHERE key=?", (ckey,)).fetchone()
            if row:
                import json as _j
                if _time.time() - row[1] < (row[2] or ttl):
                    return {"ok": True, "data": _j.loads(row[0]), "cached": True}
        except Exception:
            pass
    r = call(provider, "GET", url, headers=headers, params=params)
    if r.get("ok"):
        try:
            import json as _j
            db = _db()
            db.execute("INSERT OR REPLACE INTO provider_cache(key, body, ts, ttl) VALUES(?,?,?,?)",
                       (ckey, _j.dumps(r["data"])[:50000], _time.time(), ttl))
            db.commit()
        except Exception:
            pass
    return r


def health(provider: str = ""):
    """Per-provider reliability numbers for the dashboard."""
    try:
        if provider:
            rows = _db().execute(
                "SELECT provider, calls, fails, ms_total FROM provider_health WHERE provider=?",
                (provider,)).fetchall()
        else:
            rows = _db().execute("SELECT provider, calls, fails, ms_total FROM provider_health").fetchall()
    except Exception:
        rows = []
    out = []
    for p, calls, fails, ms in rows:
        out.append({"provider": p, "calls": calls, "fails": fails,
                    "fail_rate": round(fails / max(1, calls), 3),
                    "avg_ms": round(ms / max(1, calls)),
                    "circuit": "open" if breaker_state(p)["until"] > _time.time() else "closed"})
    return out
