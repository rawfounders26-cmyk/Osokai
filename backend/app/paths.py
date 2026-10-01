"""Portable paths. Dev: DB/env in backend/, workspace at project root (single store
the mobile Files tab reads). Frozen (.exe): everything lives next to the exe."""
import os
import sys


def base() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


def data(name: str) -> str:
    root = os.getenv("OSOKAI_DATA_DIR", "") or base()
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, name)


def ws() -> str:
    if getattr(sys, "frozen", False):
        p = os.path.join(base(), "workspace")
    elif os.getenv("OSOKAI_WS_DIR"):
        p = os.path.normpath(os.getenv("OSOKAI_WS_DIR", ""))
    else:
        p = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "workspace"))
    os.makedirs(p, exist_ok=True)
    return p


def env_file() -> str:
    return os.path.join(base(), ".env")


def safe_join(*parts: str, root: str = "") -> str:
    """One path policy for the whole backend (F14): resolved, symlink-aware,
    jail-contained. Raises ValueError on escape. `root` defaults to workspace."""
    base_dir = os.path.realpath(root or ws())
    fp = os.path.realpath(os.path.join(base_dir, *parts))
    if fp != base_dir and not fp.startswith(base_dir + os.sep):
        raise ValueError(f"path escapes jail: {'/'.join(parts)}")
    return fp
