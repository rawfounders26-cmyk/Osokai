"""Injection guards — prompt-injection defense, scaled.

Scans untrusted text (tool outputs, web content, pasted messages) for
instruction-override patterns. Patterns precompile once at import (1000x:
scan cost is microseconds, safe on every tool output). verify.execute routes
web/fetch results through here — hits annotate evidence and force a verify
re-check, so smuggled instructions can't silently become accepted work.
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
    r"system\s*:\s*you must",
    r"\[system\]",
    r"as\s+an\s+ai\s+with\s+no\s+restrictions",
    r"transfer\s+.*\b\d{4,}\b.*to\b",
    r"confirm\s+that\s+you\s+sent",
    r"mark\s+.*as\s+(done|complete|paid)",
]

_COMPILED = [re.compile(p, re.I) for p in PATTERNS]
_COMPILED_SUB = [(re.compile(f"({p})", re.I)) for p in PATTERNS]


def scan(text: str):
    """Return {clean: bool, hits: [patterns]}. Precompiled — microseconds."""
    t = text or ""
    hits = [PATTERNS[i] for i, rx in enumerate(_COMPILED) if rx.search(t)]
    return {"clean": not hits, "hits": hits}


def scrub(text: str) -> str:
    """Wrap hits in markers so downstream prompts treat them as data, not orders."""
    t = text or ""
    for rx in _COMPILED_SUB:
        t = rx.sub(r"[UNTRUSTED:\1]", t)
    return t
