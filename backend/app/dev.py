"""Dev tools — sandboxed shell + git, workspace-only. No system dirs, no destructive cmds."""
import os
import shlex
import subprocess

try:
    from app.paths import ws as _pws
except ImportError:
    from paths import ws as _pws

WS = _pws()

ALLOW = ("python", "pip", "pytest", "node", "npm", "git", "dir", "ls", "echo", "code")
# shell metacharacters never reach an interpreter: no shell=True, ever (F02)
META = (";", "|", "&", "$", "`", "<", ">", "(", ")", "{", "}", "\\", "\n", "\r")


def _jail_arg(a: str) -> str:
    """Paths must stay under workspace/."""
    if ".." in a.replace("\\", "/").split("/"):
        raise ValueError("path escapes workspace")
    return a


def shell(cmd: str, timeout: int = 60) -> str:
    """Run an allowlisted command inside workspace/ via arg array (no shell).
    Returns output (truncated). Anything outside the allowlist/metachar rules
    is refused before execution."""
    c = (cmd or "").strip()
    if not c:
        return "(empty command)"
    if any(m in c for m in META):
        return "(blocked: shell metacharacters not allowed)"
    try:
        argv = shlex.split(c, posix=True)
    except Exception:
        return "(blocked: cannot parse command)"
    if not argv:
        return "(empty command)"
    first = argv[0].lower().split("/")[-1]
    if first not in ALLOW:
        return f"(blocked: '{argv[0]}' not in allowlist)"
    if first in ("python", "node") and any(a == "-c" for a in argv[1:]):
        return "(blocked: inline code (-c) not allowed — run a workspace file)"
    for a in argv[1:]:
        try:
            _jail_arg(a)
        except ValueError as e:
            return f"(blocked: {e})"
    if first == "echo":
        return " ".join(argv[1:])[:4000] or ""
    if first in ("dir", "ls"):
        try:
            target = _jail_arg(argv[1]) if len(argv) > 1 else ""
            base = os.path.normpath(os.path.join(WS, target))
            return "\n".join(sorted(os.listdir(base)))[:4000] or "(empty)"
        except ValueError as e:
            return f"(blocked: {e})"
        except Exception as e:
            return f"(error: {e})"
    return _run_argv(argv, timeout)


def _run_argv(argv, timeout: int = 60) -> str:
    try:
        argv = [argv[0]] + [_jail_arg(a) for a in argv[1:]]
    except ValueError as e:
        return f"(blocked: {e})"
    try:
        r = subprocess.run(argv, shell=False, cwd=WS, capture_output=True, text=True, timeout=timeout)
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
        m = "".join(ch for ch in (msg or "osok-ai checkpoint") if ch not in META)[:120] or "osok-ai checkpoint"
        a = _run_argv(["git", "add", "-A"], 60)
        b = _run_argv(["git", "commit", "-m", m], 60)
        return a + "\n" + b
    if op == "init":
        return shell("git init")
    return "(unknown git op: status|diff|log|commit|init)"
