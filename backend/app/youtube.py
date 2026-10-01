"""YouTube read — our own design. Public channel RSS (no credentials, works live):
latest videos from any channel. Search uses the existing web_search path.
Feeds the taste/onboarding + creator loop without API keys or quotas.
"""
import re as _re


def _channel_id(url_or_id: str) -> str:
    s = (url_or_id or "").strip()
    m = _re.search(r"(?:youtube\.com/(?:channel/|@)|youtu\.be/)([A-Za-z0-9_-]+)", s)
    if m and not s.startswith("@") and "channel/" in s:
        return m.group(1)
    if _re.fullmatch(r"[A-Za-z0-9_-]{10,}", s):
        return s
    return ""


def _parse_feed(xml_text: str, cid: str, limit: int = 8):
    """Pure XML -> video list. Deterministic, unit-tested without network."""
    import xml.etree.ElementTree as _et
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = _et.fromstring(xml_text)
    out = []
    for e in root.findall("a:entry", ns)[:max(1, min(20, limit))]:
        vid = (e.findtext("a:id", default="", namespaces=ns) or "").split(":")[-1]
        out.append({"id": vid,
                    "title": e.findtext("a:title", default="", namespaces=ns),
                    "published": (e.findtext("a:published", default="", namespaces=ns) or "")[:10],
                    "url": f"https://youtu.be/{vid}" if vid else ""})
    return out


def latest_videos(channel: str, limit: int = 8):
    """Latest uploads via public RSS. No key, no quota, live data."""
    cid = _channel_id(channel)
    if not cid:
        return {"ok": False, "error": "need a channel ID or channel URL (handles need resolving first)"}
    import httpx as _hx  # raw fetch: RSS is XML, not JSON (transport is JSON-oriented)
    try:
        r = _hx.get("https://www.youtube.com/feeds/videos.xml",
                    params={"channel_id": cid}, timeout=20,
                    headers={"User-Agent": "Osok-AI/1.0"})
        if r.status_code != 200:
            return {"ok": False, "error": f"feed failed: {r.status_code}"}
        return {"ok": True, "channel": cid, "videos": _parse_feed(r.text, cid, limit)}
    except Exception as e:
        return {"ok": False, "error": f"feed read failed: {e}"[:200]}
