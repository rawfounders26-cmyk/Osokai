"""Dev tools — sandboxed shell + git, workspace-only. No system dirs, no destructive cmds."""
import os
import subprocess

try:
    from app.paths import ws as _pws
except ImportError:
    from paths import ws as _pws

WS = _pws()

ALLOW = ("python", "pip", "pytest", "node", "npm", "git", "dir", "ls", "echo", "code")
BLOCKED = ("rm ", "del ", "format", "shutdown", "reboot", ":(){", "mkfs", "dd ")


def shell(cmd: str, timeout: int = 60) -> str:
    """Run an allowlisted command inside workspace/. Returns output (truncated)."""
    c = (cmd or "").strip()
    if not c:
        return "(empty command)"
    low = c.lower()
    if any(b in low for b in BLOCKED):
        return "(blocked: destructive command)"
    first = low.split()[0].split("/")[-1].split("\\")[-1]
    if first not in ALLOW and not first.endswith((".py", ".js")):
        return f"(blocked: '{first}' not in allowlist)"
    try:
        r = subprocess.run(c, shell=True, cwd=WS, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "") + ("\nERR:" + r.stderr if r.stderr else "")
        return (out.strip() or f"(exit {r.returncode}, no output)")[:4000]
    except subprocess.TimeoutExpired:
        return "(timed out)"
    except Exception as e:
        return f"(error: {e})"


def git(op: str, msg: str = "") -> str:
    """Safe git ops inside workspace: status, diff, log, commit."""
    op = (op or "").lower()
    if op == "status":
        return shell("git status --short")
    if op == "diff":
        return shell("git diff --stat")
    if op == "log":
        return shell("git log --oneline -10")
    if op == "commit":
        m = (msg or "osok-ai checkpoint").replace('"', "'")
        return shell(f'git add -A && git commit -m "{m}"')
    if op == "init":
        return shell("git init")
    return "(unknown git op: status|diff|log|commit|init)"
