"""Wake-word + streaming voice — hands-free surface, zero new deps.

- PCM energy VAD (16-bit mono): speech/silence per chunk, no model needed.
- Wake config: keyword + energy threshold + cooldown, served to clients
  (true on-device keyword spotting lands client-side; server gates + routes).
- Stream sessions: chunks in -> VAD state out; on speech-end, buffered audio
  auto-transcribes via Groq whisper and returns text ready for /voice/command.
"""
import base64
import os
import sqlite3
import struct
import time

try:
    from app.paths import data as _pdata
except ImportError:
    from paths import data as _pdata

try:
    from app.db import connect as _hardb
except ImportError:
    from db import connect as _hardb
DB = _pdata("osokai.db")
SILENCE_END_MS = 900


def _db():
    db = _hardb(os.path.normpath(DB))
    db.execute("CREATE TABLE IF NOT EXISTS wake_cfg(id INTEGER PRIMARY KEY CHECK(id=1), keyword TEXT, threshold REAL, cooldown INT)")
    return db


def get_config() -> dict:
    try:
        r = _db().execute("SELECT keyword, threshold, cooldown FROM wake_cfg WHERE id=1").fetchone()
        if r:
            return {"keyword": r[0], "threshold": r[1], "cooldown_s": r[2]}
    except Exception:
        pass
    return {"keyword": "hey osok", "threshold": 400.0, "cooldown_s": 5}


def set_config(keyword: str = "", threshold: float = 0, cooldown: int = 0) -> dict:
    cur = get_config()
    db = _db()
    db.execute("INSERT OR REPLACE INTO wake_cfg(id, keyword, threshold, cooldown) VALUES(1,?,?,?)",
               (keyword or cur["keyword"], threshold or cur["threshold"], cooldown or cur["cooldown_s"]))
    db.commit()
    return get_config()


def vad(pcm: bytes, threshold: float = 0) -> dict:
    """Frame energy gate. Returns {speech, energy}. Works on raw s16le mono."""
    th = threshold or get_config()["threshold"]
    if len(pcm) < 2:
        return {"speech": False, "energy": 0.0}
    n = len(pcm) // 2
    fmt = "<" + "h" * n
    try:
        samples = struct.unpack(fmt, pcm[:n * 2])
    except Exception:
        return {"speech": False, "energy": 0.0}
    energy = (sum(s * s for s in samples) / n) ** 0.5
    return {"speech": energy >= th, "energy": round(energy, 1)}


_sessions: dict = {}


def stream_start() -> str:
    import uuid as _u
    sid = _u.uuid4().hex[:12]
    _sessions[sid] = {"buf": bytearray(), "silence_ms": 0, "heard": False, "ts": time.time()}
    return sid


def stream_chunk(sid: str, audio_b64: str, ms: int = 100) -> dict:
    s = _sessions.get(sid)
    if not s:
        return {"ok": False, "error": "no such stream"}
    try:
        pcm = base64.b64decode(audio_b64)
    except Exception:
        return {"ok": False, "error": "bad audio_b64"}
    v = vad(pcm)
    s["buf"].extend(pcm)
    if v["speech"]:
        s["heard"] = True
        s["silence_ms"] = 0
    else:
        s["silence_ms"] += ms
    s["ts"] = time.time()
    ended = s["heard"] and s["silence_ms"] >= SILENCE_END_MS
    if len(s["buf"]) > 20 * 1024 * 1024:
        return {"ok": False, "error": "stream too long (20MB max)"}
    return {"ok": True, "speech": v["speech"], "energy": v["energy"],
            "ended": ended, "bytes": len(s["buf"])}


def stream_finish(sid: str) -> dict:
    s = _sessions.pop(sid, None)
    if not s or not s["buf"]:
        return {"ok": False, "error": "empty stream"}
    import httpx as _hx
    key = os.getenv("GROQ_API_KEY", "") or os.getenv("GROK_API_KEY", "")
    if not key.startswith("gsk_"):
        return {"ok": False, "error": "voice needs a Groq (gsk_) key"}
    try:
        r = _hx.post("https://api.groq.com/openai/v1/audio/transcriptions",
                     headers={"Authorization": f"Bearer {key}"},
                     files={"file": ("voice.pcm", bytes(s["buf"]))},
                     data={"model": "whisper-large-v3-turbo"}, timeout=120)
        if r.status_code != 200:
            return {"ok": False, "error": f"transcribe failed: {r.text[:150]}"}
        text = r.json().get("text", "")
        return {"ok": True, "text": text,
                "command": {"hint": "POST this text to /voice/command", "text": text}}
    except Exception as e:
        return {"ok": False, "error": f"transcribe failed: {e}"}
