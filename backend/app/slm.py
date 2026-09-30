"""SLM slot — on-device small model provider interface.

Tries local backends in order (llama-cpp-python, transformers, onnxruntime)
using OSOKAI_SLM_MODEL / OSOKAI_SLM_BACKEND. Nothing installed -> escalate
to Groq with zero behavior change. When weights land, the fast lane's
SLM-zone (confidence 0.5-0.9) answers locally with no code change.
"""
import os

BACKENDS = ("llama_cpp", "transformers", "onnx")
MAX_FETCH_MB = int(os.getenv("OSOKAI_SLM_MAX_MB", "4500"))


def _cfg_path() -> str:
    try:
        from app.paths import data as _pd
    except ImportError:
        from paths import data as _pd
    return _pd("slm.json")


def _cfg_get() -> dict:
    import json as _j
    try:
        return _j.load(open(_cfg_path(), encoding="utf-8"))
    except Exception:
        return {}


def _cfg_set(patch: dict) -> dict:
    import json as _j
    cfg = {**_cfg_get(), **patch}
    try:
        open(_cfg_path(), "w", encoding="utf-8").write(_j.dumps(cfg))
    except Exception:
        pass
    return cfg


def weights_dir() -> str:
    try:
        from app.paths import data as _pd
    except ImportError:
        from paths import data as _pd
    d = os.path.join(os.path.dirname(_pd("x")), "weights")
    os.makedirs(d, exist_ok=True)
    return d


def _model_path() -> str:
    return os.getenv("OSOKAI_SLM_MODEL", "") or _cfg_get().get("model", "")


def _want() -> str:
    return os.getenv("OSOKAI_SLM_BACKEND", "auto").lower()


def _has(mod: str) -> bool:
    import importlib.util as _u
    try:
        return _u.find_spec(mod) is not None
    except Exception:
        return False


def status() -> dict:
    avail = []
    if _has("llama_cpp"):
        avail.append("llama_cpp")
    if _has("transformers"):
        avail.append("transformers")
    if _has("onnxruntime"):
        avail.append("onnx")
    want = _want()
    active = want if want in avail else (avail[0] if avail else "")
    return {"available": active or False, "backend": active or None,
            "candidates": avail, "model": _model_path() or None,
            "hint": "set OSOKAI_SLM_MODEL to a weights path; pip install llama-cpp-python" if not active else "ready"}


_engine = None


def _engine_llama_cpp():
    global _engine
    if _engine is None:
        from llama_cpp import Llama
        _engine = Llama(model_path=_model_path(), n_ctx=2048, verbose=False)
    return _engine


def generate(prompt: str, max_tokens: int = 200) -> str:
    """Return local completion or raise RuntimeError('no-slm') to escalate."""
    st = status()
    if not st["available"]:
        raise RuntimeError("no-slm")
    if st["backend"] == "llama_cpp":
        out = _engine_llama_cpp()(prompt, max_tokens=max_tokens, stop=["\n\n"])
        return out["choices"][0]["text"].strip()
    raise RuntimeError("no-slm")  # transformers/onnx wired per-model; escalate meanwhile


def fetch_weights(url: str) -> dict:
    """Drop-in: stream weights from a URL into the slot, verify, flip traffic.
    GGUF verified by magic bytes; other formats accepted on size alone.
    Traffic flips automatically — status() goes ready, SLM-zone routes local."""
    import httpx as _hx
    url = (url or "").strip()
    if not url.startswith(("https://", "http://")):
        return {"ok": False, "error": "https URL required"}
    name = url.split("?")[0].rstrip("/").split("/")[-1] or "model.gguf"
    if any(c in name for c in ("/", "\\", "..")):
        return {"ok": False, "error": "bad filename"}
    dest = os.path.join(weights_dir(), name)
    try:
        downloaded = 0
        with _hx.stream("GET", url, timeout=60, follow_redirects=True) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_bytes(1024 * 256):
                    downloaded += len(chunk)
                    if downloaded > MAX_FETCH_MB * 1024 * 1024:
                        f.close()
                        os.remove(dest)
                        return {"ok": False, "error": f"exceeds {MAX_FETCH_MB}MB cap"}
                    f.write(chunk)
        if downloaded < 1024 * 1024:
            os.remove(dest)
            return {"ok": False, "error": "file too small to be weights"}
        if name.endswith(".gguf"):
            with open(dest, "rb") as f:
                if f.read(4) != b"GGUF":
                    os.remove(dest)
                    return {"ok": False, "error": "not a GGUF file"}
        _cfg_set({"model": dest, "fetched": url})
        return {"ok": True, "model": dest, "mb": round(downloaded / 1024 / 1024, 1),
                "note": "weights in slot — install a backend (pip install llama-cpp-python) to flip traffic local"}
    except Exception as e:
        try:
            os.remove(dest)
        except Exception:
            pass
        return {"ok": False, "error": f"fetch failed: {e}"[:200]}
