"""SLM slot — on-device small model provider interface.

Tries local backends in order (llama-cpp-python, transformers, onnxruntime)
using OSOKAI_SLM_MODEL / OSOKAI_SLM_BACKEND. Nothing installed -> escalate
to Groq with zero behavior change. When weights land, the fast lane's
SLM-zone (confidence 0.5-0.9) answers locally with no code change.
"""
import os

BACKENDS = ("llama_cpp", "transformers", "onnx")


def _model_path() -> str:
    return os.getenv("OSOKAI_SLM_MODEL", "")


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
