"""Image tools — resize, convert, compress, meme-text, thumbnails.
Works on workspace/ files (same store mobile Files shows)."""
import os

try:
    WS = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "workspace"))
except Exception:
    WS = "workspace"

def _open(name: str):
    from PIL import Image
    fp = os.path.normpath(os.path.join(WS, name))
    if not fp.startswith(WS) or not os.path.isfile(fp):
        raise ValueError(f"not in workspace: {name}")
    img = Image.open(fp)
    img.load()
    return img, fp

def _save(img, name: str, quality: int = 85):
    fp = os.path.join(WS, name)
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
