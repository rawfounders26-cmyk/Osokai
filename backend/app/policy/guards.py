"""Injection guards — prompt-injection defense basics.

Scans untrusted text (tool outputs, web content, pasted messages) for
instruction-override patterns. Returns {clean, hits}. Callers decide:
critic input flagged → escalate; chat input flagged → confirm intent.
Deterministic patterns first; model-based judgment later.
"""
import re

PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+.*instructions",
    r"you\s+are\s+now\s+",
    r"new\s+system\s+prompt",
    r"jailbreak",
    r"bypass\s+(the\s+)?(approval|safety|permission)",
    r"send\s+.*password\s+to\b",
    r"reveal\s+.*(password|secret|key|token)",
    r"execute\s+.*rm\s+-rf",
    r"disable\s+(safety|approval|guard)",
    r"pretend\s+(you\s+are|to\s+be)",
    r"do\s+not\s+tell\s+the\s+user",
]


def scan(text: str):
    """Return {clean: bool, hits: [patterns]}. Case-insensitive, cheap."""
    t = text or ""
    hits = [p for p in PATTERNS if re.search(p, t, re.I)]
    return {"clean": not hits, "hits": hits}


def scrub(text: str) -> str:
    """Wrap hits in markers so downstream prompts treat them as data, not orders."""
    t = text or ""
    for p in PATTERNS:
        t = re.sub(f"({p})", r"[UNTRUSTED:\1]", t, flags=re.I)
    return t
