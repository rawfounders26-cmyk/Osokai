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


# Hot-path indexes (1000x: every frequent WHERE/ORDER/JOIN covered). Idempotent.
INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_turns_ts ON turns(ts)",
    "CREATE INDEX IF NOT EXISTS idx_turns_role_ts ON turns(role, ts)",
    "CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status)",
    "CREATE INDEX IF NOT EXISTS idx_loops_status ON loops(status)",
    "CREATE INDEX IF NOT EXISTS idx_loops_due ON loops(due)",
    "CREATE INDEX IF NOT EXISTS idx_objectives_gid ON objectives(gid)",
    "CREATE INDEX IF NOT EXISTS idx_projects_oid ON projects(oid)",
    "CREATE INDEX IF NOT EXISTS idx_gtasks_pid ON gtasks(pid)",
    "CREATE INDEX IF NOT EXISTS idx_gtasks_status ON gtasks(status)",
    "CREATE INDEX IF NOT EXISTS idx_subtasks_tid ON subtasks(tid)",
    "CREATE INDEX IF NOT EXISTS idx_subtasks_status ON subtasks(status)",
    "CREATE INDEX IF NOT EXISTS idx_nudges_seen_ts ON nudges(seen, ts)",
    "CREATE INDEX IF NOT EXISTS idx_usage_ts ON usage_log(ts)",
    "CREATE INDEX IF NOT EXISTS idx_usage_actor ON usage_log(actor)",
    "CREATE INDEX IF NOT EXISTS idx_outbox_dev ON outbox(device, delivered)",
    "CREATE INDEX IF NOT EXISTS idx_relay_dev ON relay_inbox(device, delivered)",
    "CREATE INDEX IF NOT EXISTS idx_e2e_dev ON e2e_inbox(device, delivered)",
    "CREATE INDEX IF NOT EXISTS idx_cal_day ON cal_events(day)",
    "CREATE INDEX IF NOT EXISTS idx_cal_done ON cal_events(done)",
    "CREATE INDEX IF NOT EXISTS idx_exp_gid_ts ON bill_expenses(gid, ts)",
    "CREATE INDEX IF NOT EXISTS idx_splits_eid ON bill_splits(eid)",
    "CREATE INDEX IF NOT EXISTS idx_settle_gid ON bill_settle(gid)",
    "CREATE INDEX IF NOT EXISTS idx_episodes_ts ON mem_episodes(ts)",
    "CREATE INDEX IF NOT EXISTS idx_facts_ts ON facts(ts)",
    "CREATE INDEX IF NOT EXISTS idx_runs_job ON schedule_runs(job)",
    "CREATE INDEX IF NOT EXISTS idx_orch_gid ON orch_log(gid)",
    "CREATE INDEX IF NOT EXISTS idx_taskruns_status ON task_runs(status)",
    "CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)",
    "CREATE INDEX IF NOT EXISTS idx_wardrobe_worn ON wardrobe(last_worn)",
    "CREATE INDEX IF NOT EXISTS idx_digest_ts ON digests(ts)",
    "CREATE INDEX IF NOT EXISTS idx_audit_ts ON runtime_audit(ts)",
]


def ensure_indexes(path: str) -> int:
    """Create all hot-path indexes. Safe to run every startup. Returns count."""
    db = connect(path)
    n = 0
    for stmt in INDEXES:
        try:
            db.execute(stmt)
            n += 1
        except Exception:
            pass
    try:
        db.commit()
    except Exception:
        pass
    try:
        db.close()
    except Exception:
        pass
    return n
