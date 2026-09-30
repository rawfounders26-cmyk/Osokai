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
    try:
        r = _client.post(
            url,
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": message}],
                  "max_tokens": 600},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[osok-ai-error] LLM call failed: {e}"
