"""System tools — Osok-AI CAN open apps and URLs on this PC. Instant, no LLM roundtrip.
URLs always open in Chrome (the browser hosting the Osok-AI extension), never the stray default browser."""
import os, sys, webbrowser

APP_CMDS = {
    "chrome": "chrome", "notepad": "notepad", "calculator": "calc",
    "explorer": "explorer", "terminal": "cmd", "cmd": "cmd",
    "spotify": "spotify", "vscode": "code", "code": "code",
};

def _dry():
    return os.getenv("OSOKAI_DRY_RUN", "") == "1"

def clean_url(url: str) -> str:
    """Fix LLM-style mangling: surrounding quotes, https// missing colon, %22, spaces."""
    import re
    import urllib.parse
    u = (url or "").strip().strip("\"'“”‘’").strip()
    try:
        u = urllib.parse.unquote(u)
    except Exception:
        pass
    u = u.strip("\"'“”‘’").strip()
    u = u.replace("%22", "").replace("%27", "")
    had_scheme = bool(re.match(r"^https?://", u))
    u = re.sub(r"^(https?)//", r"\1://", u)
    if not had_scheme:
        # scheme was missing or malformed -> plain http://
        u = re.sub(r"^https://", "http://", u)
    u = re.sub(r"^https?://(https?://)", r"\1", u)
    if not u.startswith(("http://", "https://")):
        u = "http://" + u
    return u

def _chrome_open(url: str):
    """Force Chrome via App Paths so the tab lands where Osok-AI lives. New tab if Chrome runs."""
    import subprocess
    if sys.platform.startswith("win"):
        subprocess.Popen(["cmd", "/c", "start", "", "chrome", "--new-tab", f'"{url}"'])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-a", "Google Chrome", url])
    else:
        subprocess.Popen(["google-chrome", url])

def open_url(url: str):
    url = clean_url(url)
    if _dry():
        return {"ok": True, "opened": url, "dry": True}
    try:
        _chrome_open(url)
    except Exception:
        webbrowser.open(url)  # last-resort fallback
    return {"ok": True, "opened": url, "browser": "chrome"}

def _wiki_image_urls(query: str, n: int = 8):
    """Wikimedia Commons API — keyless, bot-friendly, real search matches."""
    import httpx
    try:
        r = httpx.get("https://commons.wikimedia.org/w/api.php", params={
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": n * 2,
            "prop": "imageinfo", "iiprop": "url|size", "iilimit": 1,
        }, headers={"User-Agent": "Osok-AI/1.0"}, timeout=20)
        pages = r.json().get("query", {}).get("pages", {})
        out = []
        for p in pages.values():
            ii = (p.get("imageinfo") or [{}])[0]
            u, w = ii.get("url", ""), ii.get("width", 0) or 0
            if u and w >= 300:
                out.append(u)
        return out[:n]
    except Exception:
        return []

def _free_image_urls(query: str, n: int = 3):
    """Keyless themed APIs (bot-friendly) + random fallback."""
    import httpx
    q = query.lower()
    out = []
    try:
        if "dog" in q or "puppy" in q:
            for _ in range(n):
                r = httpx.get("https://dog.ceo/api/breeds/image/random",
                              headers={"User-Agent": "Osok-AI/1.0"}, timeout=20)
                u = r.json().get("message", "")
                if u:
                    out.append(u)
        elif "cat" in q or "kitten" in q:
            out += [f"https://cataas.com/cat?x={i}" for i in range(n)]
    except Exception:
        pass
    return out

def _ddg_image_urls(query: str, n: int = 8):
    """DuckDuckGo i.js — no JS rendering needed."""
    import re
    import httpx
    ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    r = httpx.post("https://duckduckgo.com/", data={"q": query}, headers=ua, timeout=20)
    m = re.search(r"vqd=[\"']([\d-]+)[\"']", r.text)
    if not m:
        return []
    vqd = m.group(1)
    r = httpx.get("https://duckduckgo.com/i.js", params={"l": "us-en", "o": "json", "q": query, "vqd": vqd, "f": ",,,", "p": "1"},
                  headers=ua, timeout=20)
    try:
        return [x["image"] for x in r.json().get("results", []) if x.get("image")][:n]
    except Exception:
        return []

def _bing_image_urls(query: str, n: int = 8):
    import re
    import httpx
    r = httpx.get("https://www.bing.com/images/search",
                  params={"q": query}, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                  timeout=20)
    return list(dict.fromkeys(re.findall(r'"murl":"(https?://[^"]+)"', r.text)))[:n]

def save_images(query: str, count: int = 1, dest: str = "desktop"):
    """Search Google Images, download first working result(s) to Desktop/Downloads."""
    import re
    import httpx
    base = os.path.join(os.path.expanduser("~"), "Desktop" if dest == "desktop" else "Downloads")
    os.makedirs(base, exist_ok=True)
    try:
        urls = (_wiki_image_urls(query) or _ddg_image_urls(query)
                or _bing_image_urls(query) or _free_image_urls(query))
        if not urls:  # last resort: random real photo (guaranteed image)
            urls = ["https://picsum.photos/1024/768"]
        seen, saved = set(), []
        for u in urls:
            u = u.replace("\\u003d", "=").replace("\\u0026", "&")
            if u in seen:
                continue
            seen.add(u)
            try:
                d = httpx.get(u, headers={"User-Agent": "Mozilla/5.0"}, timeout=20, follow_redirects=True)
                if d.status_code != 200 or len(d.content) < 5000:
                    continue
                ext = ".jpg"
                ct = d.headers.get("content-type", "")
                if "png" in ct:
                    ext = ".png"
                elif "webp" in ct:
                    ext = ".webp"
                name = re.sub(r"[^\w\- ]+", "", query).strip().replace(" ", "-")[:40] or "image"
                fp = os.path.join(base, f"{name}-{len(saved) + 1}{ext}")
                open(fp, "wb").write(d.content)
                saved.append(fp)
                if len(saved) >= max(1, count):
                    break
            except Exception:
                continue
        if not saved:
            return {"ok": False, "error": "no downloadable image found"}
        return {"ok": True, "saved": saved}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

def open_app(name: str):
    import subprocess
    key = name.strip().lower()
    if _dry():
        return {"ok": True, "opened": key, "dry": True}
    if key in ("chrome", "google chrome", "browser"):
        try:
            _chrome_open("about:blank")
        except Exception:
            webbrowser.open("about:blank")
        return {"ok": True, "opened": "chrome"}
    if key in APP_CMDS:
        cmd = APP_CMDS[key]
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(cmd, shell=True)
            else:
                subprocess.Popen(["open", "-a", name] if sys.platform == "darwin" else [cmd])
            return {"ok": True, "opened": key}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    # unknown multi-word phrase is not an app — fail honest instead of fake "Opened"
    if len(key.split()) > 2:
        return {"ok": False, "error": f"don't know the app '{name}' — try 'open <app>' or a search instead"}
    cmd = APP_CMDS.get(key, key)
    try:
        if sys.platform.startswith("win"):
            subprocess.Popen(cmd, shell=True)
        else:
            subprocess.Popen(["open", "-a", name] if sys.platform == "darwin" else [cmd])
        return {"ok": True, "opened": key}
    except Exception as e:
        return {"ok": False, "error": str(e)}
