"""Team mode — the wedge into shared work.

Teams own members, shared goal trees, and multi-user approvals: any member
can resolve a team approval, and every resolution is attributed. Personal
data stays personal — only explicitly shared goals and team approvals cross
the boundary.
"""
import os
import sqlite3
import time

try:
    from app.paths import data as _pdata
except ImportError:
    from paths import data as _pdata

DB = _pdata("osokai.db")


def _db():
    db = sqlite3.connect(os.path.normpath(DB), check_same_thread=False)
    db.execute("CREATE TABLE IF NOT EXISTS teams(id INTEGER PRIMARY KEY, name TEXT, ts REAL)")
    db.execute("""CREATE TABLE IF NOT EXISTS team_members(
        team INT, user TEXT, role TEXT, ts REAL, PRIMARY KEY(team, user))""")
    db.execute("CREATE TABLE IF NOT EXISTS goal_shares(gid INT, team INT, ts REAL, PRIMARY KEY(gid, team))")
    db.execute("""CREATE TABLE IF NOT EXISTS team_approvals(
        id INTEGER PRIMARY KEY, team INT, message TEXT, kind TEXT, item TEXT,
        status TEXT DEFAULT 'pending', by_user TEXT DEFAULT '', ts REAL)""")
    db.execute("CREATE TABLE IF NOT EXISTS team_budgets(team INT PRIMARY KEY, cap_usd REAL)")
    return db


ROLES = ("viewer", "member", "admin", "owner")


def role_of(tid: int, user: str) -> str:
    r = _db().execute("SELECT role FROM team_members WHERE team=? AND user=?", (tid, user)).fetchone()
    return r[0] if r and r[0] in ROLES else ""


def can(tid: int, user: str, action: str) -> bool:
    """viewer reads; member resolves + shares; admin manages members/budgets; owner all."""
    need = {"read": 0, "resolve": 1, "share": 1, "manage": 2, "owner": 3}.get(action, 3)
    have = ROLES.index(role_of(tid, user)) if role_of(tid, user) in ROLES else -1
    return have >= need


def set_role(tid: int, admin: str, user: str, role: str) -> dict:
    if role not in ROLES:
        return {"ok": False, "error": "bad role"}
    if not can(tid, admin, "manage"):
        return {"ok": False, "error": "admin only"}
    if role_of(tid, user) == "owner" and role != "owner":
        return {"ok": False, "error": "cannot demote the owner"}
    db = _db()
    db.execute("INSERT OR REPLACE INTO team_members(team, user, role, ts) VALUES(?,?,?,?)",
               (tid, user[:120], role, time.time()))
    db.commit()
    return {"ok": True}


def set_budget(tid: int, admin: str, cap_usd: float) -> dict:
    if not can(tid, admin, "manage"):
        return {"ok": False, "error": "admin only"}
    db = _db()
    db.execute("INSERT OR REPLACE INTO team_budgets(team, cap_usd) VALUES(?,?)", (tid, max(0.0, cap_usd)))
    db.commit()
    return {"ok": True}


def spend(tid: int) -> dict:
    """Per-seat AI spend: usage rows whose actor matches a team member."""
    db = _db()
    members = [r[0] for r in db.execute("SELECT user FROM team_members WHERE team=?", (tid,))]
    cap = db.execute("SELECT cap_usd FROM team_budgets WHERE team=?", (tid,)).fetchone()
    cap = cap[0] if cap else 0.0
    seats, total = [], 0.0
    try:
        try:
            from app.usage import PRICE_PER_1K, _db as _udb
        except ImportError:
            from usage import PRICE_PER_1K, _db as _udb
        udb = _udb()
        for m in members:
            r = udb.execute("SELECT COUNT(*), SUM(tokens) FROM usage_log WHERE actor=?", (m,)).fetchone()
            cost = round((r[1] or 0) / 1000 * PRICE_PER_1K, 4)
            total += cost
            seats.append({"user": m, "role": role_of(tid, m), "calls": r[0], "cost_usd": cost})
    except Exception:
        pass
    total = round(total, 4)
    return {"team": tid, "seats": seats, "total_usd": total, "cap_usd": cap,
            "over_budget": bool(cap and total >= cap)}


def create_team(name: str, owner: str = "me") -> dict:
    db = _db()
    cur = db.execute("INSERT INTO teams(name, ts) VALUES(?,?)", (name[:120], time.time()))
    tid = cur.lastrowid
    db.execute("INSERT INTO team_members(team, user, role, ts) VALUES(?,?,?,?)", (tid, owner, "owner", time.time()))
    db.commit()
    return {"ok": True, "id": tid}


def add_member(tid: int, user: str, role: str = "member") -> dict:
    db = _db()
    if not db.execute("SELECT 1 FROM teams WHERE id=?", (tid,)).fetchone():
        return {"ok": False, "error": "no such team"}
    db.execute("INSERT OR REPLACE INTO team_members(team, user, role, ts) VALUES(?,?,?,?)",
               (tid, user[:120], role, time.time()))
    db.commit()
    return {"ok": True}


def list_teams():
    db = _db()
    out = []
    for tid, name in db.execute("SELECT id, name FROM teams ORDER BY id").fetchall():
        members = [{"user": r[0], "role": r[1]} for r in
                   db.execute("SELECT user, role FROM team_members WHERE team=?", (tid,))]
        out.append({"id": tid, "name": name, "members": members})
    return out


def share_goal(gid: int, tid: int) -> dict:
    db = _db()
    if not db.execute("SELECT 1 FROM teams WHERE id=?", (tid,)).fetchone():
        return {"ok": False, "error": "no such team"}
    db.execute("INSERT OR REPLACE INTO goal_shares(gid, team, ts) VALUES(?,?,?)", (gid, tid, time.time()))
    db.commit()
    return {"ok": True}


def team_goals(tid: int):
    """Shared goal trees with progress, for the team view."""
    try:
        try:
            from app import goaltrees as _gt
        except ImportError:
            import goaltrees as _gt
    except Exception:
        return []
    db = _db()
    gids = [r[0] for r in db.execute("SELECT gid FROM goal_shares WHERE team=?", (tid,))]
    out = []
    for gid in gids:
        t = _gt.get_tree(gid)
        if t:
            out.append({"id": t["id"], "title": t["title"], "progress": t["progress"]})
    return out


def ask_team(tid: int, message: str, kind: str = "general", item: str = "") -> dict:
    db = _db()
    cur = db.execute("INSERT INTO team_approvals(team, message, kind, item, ts) VALUES(?,?,?,?,?)",
                     (tid, message[:1000], kind, item[:1000], time.time()))
    db.commit()
    return {"ok": True, "id": cur.lastrowid}


def team_pending(tid: int = 0):
    db = _db()
    q = "SELECT id, team, message, kind, item, status, by_user, ts FROM team_approvals WHERE status='pending'"
    args: tuple = ()
    if tid:
        q += " AND team=?"
        args = (tid,)
    q += " ORDER BY id"
    return [{"id": r[0], "team": r[1], "message": r[2], "kind": r[3], "item": r[4],
             "status": r[5], "by": r[6], "ts": r[7]} for r in db.execute(q, args).fetchall()]


def team_resolve(aid: int, user: str, allow: bool) -> dict:
    db = _db()
    r0 = db.execute("SELECT team FROM team_approvals WHERE id=? AND status='pending'", (aid,)).fetchone()
    if r0 and not can(r0[0], user, "resolve"):
        return {"ok": False, "error": "viewers cannot resolve approvals"}
    db.execute("UPDATE team_approvals SET status=?, by_user=? WHERE id=? AND status='pending'",
               ("allowed" if allow else "denied", user[:120], aid))
    db.commit()
    r = db.execute("SELECT id, team, message, status, by_user FROM team_approvals WHERE id=?", (aid,)).fetchone()
    return {"ok": True, "approval": {"id": r[0], "team": r[1], "message": r[2], "status": r[3], "by": r[4]} if r else None}
