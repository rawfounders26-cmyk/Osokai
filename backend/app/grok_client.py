"""LLM client — Groq (gsk_ keys, OpenAI-compatible) with xAI fallback. Key from backend/.env."""
import os
import httpx

SYSTEM = ("You are Osok-AI, a personal AI agent that CAN act on the user's computer. "
    "Simple open/play/search requests are already executed by the system before you are asked — "
    "just confirm briefly what was done. Never claim you cannot open apps, browse, or play media. "
    "Keep replies short (1-2 lines) unless asked for detail.")

_client = httpx.Client(timeout=60, limits=httpx.Limits(max_connections=10, max_keepalive_connections=5))

def chat_with_grok(message: str) -> str:
    key = os.getenv("GROQ_API_KEY", "") or os.getenv("GROK_API_KEY", "")
    model = os.getenv("GROK_MODEL", "qwen/qwen3-32b")
    if not key or key.startswith("paste-"):
        return "[osokai-stub] Set GROQ_API_KEY in backend/.env, then restart. Got: " + message[:120]
    # gsk_ = Groq Cloud, otherwise xAI
    url = "https://api.groq.com/openai/v1/chat/completions" if key.startswith("gsk_") else "https://api.x.ai/v1/chat/completions"
    import time as _t
    t0 = _t.time()
    try:
        r = _client.post(
            url,
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": message}],
                  "max_tokens": 600},
        )
        r.raise_for_status()
        try:
            from app.system_tools import sanitize_reply
        except ImportError:
            from system_tools import sanitize_reply
        reply = sanitize_reply(r.json()["choices"][0]["message"]["content"])
        try:
            try:
                from app.usage import log as _ulog
            except ImportError:
                from usage import log as _ulog
            _ulog("chat", model, message, reply, int((_t.time() - t0) * 1000))
        except Exception:
            pass
        return reply
    except Exception as e:
        return f"[osok-ai-error] LLM call failed: {e}"


def chat_with_vision(prompt: str, b64_image: str) -> str:
    """Image understanding via Groq vision model. Returns raw text (often JSON)."""
    import base64 as _b64
    key = os.getenv("GROQ_API_KEY", "") or os.getenv("GROK_API_KEY", "")
    model = os.getenv("GROK_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
    if not key or key.startswith("paste-"):
        return "[osokai-stub] Set GROQ_API_KEY in backend/.env for vision."
    if not key.startswith("gsk_"):
        return "[osok-ai-error] vision needs a Groq (gsk_) key"
    try:
        r = _client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "max_tokens": 800, "messages": [{
                "role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}]}]},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[osok-ai-error] vision call failed: {e}"
