"""Image tools — resize, convert, compress, meme-text, thumbnails.
Works on workspace/ files (same store mobile Files shows)."""
import os

try:
    from app.paths import ws as _pws
except ImportError:
    from paths import ws as _pws

WS = _pws()

def _open(name: str):
    from PIL import Image
    try:
        from app.paths import safe_join as _sj
    except ImportError:
        from paths import safe_join as _sj
    try:
        fp = _sj(name)
    except ValueError:
        raise ValueError(f"not in workspace: {name}")
    if not os.path.isfile(fp):
        raise ValueError(f"not in workspace: {name}")
    img = Image.open(fp)
    img.load()
    return img, fp

def _save(img, name: str, quality: int = 85):
    try:
        from app.paths import safe_join as _sj
    except ImportError:
        from paths import safe_join as _sj
    fp = _sj(name)
    kw = {"quality": quality, "optimize": True} if fp.lower().endswith((".jpg", ".jpeg")) else {}
    img.save(fp, **kw)
    return fp

def img_resize(name: str, width: int, height: int = 0, out: str = ""):
    from PIL import Image
    img, _ = _open(name)
    w, h = int(width), int(height or 0)
    if h <= 0:
        h = round(img.height * w / img.width)
    img = img.resize((w, h), Image.LANCZOS)
    base = os.path.splitext(os.path.basename(name))[0]
    return _save(img, out or f"{base}-{w}x{h}.jpg")

def img_convert(name: str, fmt: str = "png", out: str = ""):
    from PIL import Image
    img, _ = _open(name)
    fmt = fmt.lower().lstrip(".")
    if fmt in ("jpg", "jpeg") and img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        img = bg
    base = os.path.splitext(os.path.basename(name))[0]
    ext = "jpg" if fmt == "jpeg" else fmt
    return _save(img.convert("RGB") if ext in ("jpg",) else img, out or f"{base}.{ext}")

def img_compress(name: str, quality: int = 60, out: str = ""):
    img, _ = _open(name)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")
    base = os.path.splitext(os.path.basename(name))[0]
    return _save(img, out or f"{base}-q{quality}.jpg", quality=int(quality))

def img_thumbnail(name: str, size: int = 256, out: str = ""):
    from PIL import Image
    img, _ = _open(name)
    img.thumbnail((int(size), int(size)), Image.LANCZOS)
    base = os.path.splitext(os.path.basename(name))[0]
    return _save(img, out or f"{base}-thumb.jpg")

def img_caption(name: str, top: str = "", bottom: str = "", out: str = ""):
    """Meme-text: white Impact-style top/bottom captions with black outline."""
    from PIL import Image, ImageDraw, ImageFont
    img, _ = _open(name)
    if img.mode != "RGB":
        img = img.convert("RGB")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", max(20, img.width // 12))
    except Exception:
        font = ImageFont.load_default()
    def line(txt, y):
        bb = d.textbbox((0, 0), txt, font=font, stroke_width=2)
        x = (img.width - (bb[2] - bb[0])) // 2
        d.text((x, y), txt, font=font, fill="white", stroke_width=2, stroke_fill="black")
    if top:
        line(top.upper(), 10)
    if bottom:
        bb = d.textbbox((0, 0), bottom, font=font, stroke_width=2)
        line(bottom.upper(), img.height - (bb[3] - bb[1]) - 14)
    base = os.path.splitext(os.path.basename(name))[0]
    return _save(img, out or f"{base}-meme.jpg")


def img_generate(prompt: str, name: str = "", size: str = "1024x1024") -> str:
    """AI image generation via free Pollinations (Flux-backed, no key).
    Honest: cloud service, not local. Saves into workspace/."""
    import re
    import httpx
    from urllib.parse import quote
    w, h = 1024, 1024
    m = re.match(r"(\d+)x(\d+)", size or "")
    if m:
        w, h = max(256, min(int(m.group(1)), 2048)), max(256, min(int(m.group(2)), 2048))
    url = f"https://image.pollinations.ai/prompt/{quote(prompt[:500])}?width={w}&height={h}&nologo=true&model=flux"
    try:
        r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=120, follow_redirects=True)
        if r.status_code != 200 or len(r.content) < 20000 or "image" not in r.headers.get("content-type", ""):
            return {"ok": False, "error": f"gen failed: HTTP {r.status_code}"}
        slug = re.sub(r"[^\w\- ]+", "", prompt).strip().replace(" ", "-")[:40] or "gen"
        fp = os.path.join(WS, (name or f"{slug}.jpg"))
        if not fp.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            fp += ".jpg"
        open(fp, "wb").write(r.content)
        return {"ok": True, "saved": fp}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
