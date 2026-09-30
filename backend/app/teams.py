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
    return db


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
    db.execute("UPDATE team_approvals SET status=?, by_user=? WHERE id=? AND status='pending'",
               ("allowed" if allow else "denied", user[:120], aid))
    db.commit()
    r = db.execute("SELECT id, team, message, status, by_user FROM team_approvals WHERE id=?", (aid,)).fetchone()
    return {"ok": True, "approval": {"id": r[0], "team": r[1], "message": r[2], "status": r[3], "by": r[4]} if r else None}
