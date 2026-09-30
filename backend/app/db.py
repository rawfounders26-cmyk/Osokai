"""Shared SQLite hardening — every module connects through here.

- WAL mode: readers never block writers (scheduler + chat + proactive coexist)
- busy_timeout: brief contention waits instead of instant OperationalError
- foreign_keys: on for integrity where schemas declare them
- Same signature as sqlite3.connect so migration is one line per call site.
"""
import os
import sqlite3


def connect(path: str, check_same_thread: bool = False):
    db = sqlite3.connect(os.path.normpath(path), check_same_thread=check_same_thread)
    try:
        db.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    try:
        db.execute("PRAGMA busy_timeout=5000")
    except Exception:
        pass
    try:
        db.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass
    return db
