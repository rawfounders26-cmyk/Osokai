"""Local-first fast lane — trivial questions never leave the device.

Time/date, safe arithmetic, unit conversions, and live status queries answer
in microseconds with zero tokens. Anything else returns None and the request
escalates to Groq. This is the on-ramp to a future on-device small model:
the interface (`try_answer`) stays the same when the model arrives.
"""
import datetime
import math
import re

_CALC_SAFE = re.compile(r"^[\d\s+\-*/().%]+$")


def _calc(expr: str):
    if not _CALC_SAFE.match(expr) or not re.search(r"\d", expr):
        return None
    try:
        val = eval(compile(expr, "<calc>", "eval"), {"__builtins__": {}},  # noqa: S307 (range-checked above)
                   {k: getattr(math, k) for k in ("sqrt", "pi", "e", "pow", "log", "sin", "cos", "tan")})
        if isinstance(val, (int, float)) and abs(val) != float("inf"):
            return round(val, 6) if isinstance(val, float) else val
    except Exception:
        pass
    return None


_CONV = {
    ("km", "mi"): 0.621371, ("mi", "km"): 1.60934,
    ("kg", "lb"): 2.20462, ("lb", "kg"): 0.453592,
    ("cm", "in"): 0.393701, ("in", "cm"): 2.54,
    ("c", "f"): "c2f", ("f", "c"): "f2c",
}


def _convert(m):
    try:
        v, a, b = float(m.group(1)), m.group(2).lower(), m.group(3).lower()
    except Exception:
        return None
    k = (a, b)
    if k not in _CONV:
        return None
    f = _CONV[k]
    if f == "c2f":
        return f"{v}°C = {round(v * 9 / 5 + 32, 1)}°F"
    if f == "f2c":
        return f"{v}°F = {round((v - 32) * 5 / 9, 1)}°C"
    return f"{v:g} {a} = {round(v * f, 3):g} {b}"


def try_answer(text: str):
    """Return a local reply string, or None to escalate to the cloud model."""
    t = (text or "").strip().lower()
    if not t or len(t) > 200:
        return None
    now = datetime.datetime.now()
    if t in ("time", "time?") or re.fullmatch(r"what('s| is)?( the| current)? time( is it| now)?\??", t):
        return "It's " + now.strftime("%I:%M %p").lstrip("0") + "."
    if re.fullmatch(r"(what('s| is)? )?(today'?s? date|current date|date|day|today)(\?)?", t) or t in ("date", "date?"):
        return "Today is " + now.strftime("%A, %d %B %Y") + "."
    m = re.fullmatch(r"(what is |calculate |calc )?([\d\s+\-*/().%]+)\??", t)
    if m:
        v = _calc(m.group(2).strip())
        if v is not None:
            return f"{m.group(2).strip()} = {v}"
    m = re.fullmatch(r"convert (\d+(?:\.\d+)?)\s*([a-z°]+) to ([a-z°]+)\??", t)
    if m:
        r = _convert(m)
        if r:
            return r
    if t in ("are you online", "are you there", "ping", "status"):
        return "Online and local-first. All systems nominal."
    return None
