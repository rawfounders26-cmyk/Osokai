"""Goal trees — Goal → Objectives → Projects → Tasks → Subtasks, executable.
Templates (incl. the apartment Ex-14 pattern) seed instant trees; anything else
is compiled by the LLM into the same shape. Leaves execute via agent tools."""
import json
import sqlite3
import os
import time

try:
    from app.paths import data as _pdata
except ImportError:
    from paths import data as _pdata

try:
    from app.db import connect as _hardb
except ImportError:
    from db import connect as _hardb
DB = _pdata("osokai.db")

KINDS = ("research", "create", "browse", "approval", "human", "wait")

TEMPLATES = {
    "apartment": {
        "title": "Find an apartment",
        "objectives": [
            {"title": "Understand requirements",
             "projects": [{"title": "Apartment Search", "tasks": [
                 {"title": "Ask preferred location", "kind": "human"},
                 {"title": "Ask budget", "kind": "human"},
                 {"title": "Ask bedroom requirement", "kind": "human"}]}]},
            {"title": "Find suitable apartments",
             "projects": [{"title": "Apartment Search", "tasks": [
                 {"title": "Search property websites", "kind": "browse"},
                 {"title": "Create shortlist", "kind": "research"}]}]},
            {"title": "Compare shortlisted apartments",
             "projects": [{"title": "Apartment Comparison", "tasks": [
                 {"title": "Create comparison", "kind": "create"}]}]},
            {"title": "Arrange property visits",
             "projects": [{"title": "Property Visits", "tasks": [
                 {"title": "Contact owner", "kind": "human"},
                 {"title": "Schedule visit", "kind": "create"}]}]},
            {"title": "Prepare rental documentation",
             "projects": [{"title": "Rental Documentation", "tasks": [
                 {"title": "Create document checklist", "kind": "create"}]}]},
        ],
    },
    "startup": {
        "title": "Launch startup",
        "objectives": [
            {"title": "Validate the business idea",
             "projects": [{"title": "Market Validation", "tasks": [
                 {"title": "Research competing products", "kind": "research"},
                 {"title": "Define target customer", "kind": "research"}]}]},
            {"title": "Build the MVP",
             "projects": [{"title": "MVP Development", "tasks": [
                 {"title": "Create MVP requirements", "kind": "create"},
                 {"title": "Build landing page", "kind": "create"}]}]},
            {"title": "Prepare branding and positioning",
             "projects": [{"title": "Branding", "tasks": [
                 {"title": "Create company logo", "kind": "create"},
                 {"title": "Prepare launch announcement", "kind": "create"}]}]},
        ],
    },
    "trip": {
        "title": "Plan a trip",
        "objectives": [
            {"title": "Decide itinerary",
             "projects": [{"title": "Itinerary", "tasks": [
                 {"title": "Research destinations", "kind": "research"},
                 {"title": "Create day-by-day plan", "kind": "create"}]}]},
            {"title": "Arrange bookings",
             "projects": [{"title": "Bookings", "tasks": [
                 {"title": "Compare flights", "kind": "research"},
                 {"title": "Book flight", "kind": "approval"},
                 {"title": "Book hotels", "kind": "approval"}]}]},
        ],
    },
}


def _db():
    db = _hardb(os.path.normpath(DB))
    db.execute("""CREATE TABLE IF NOT EXISTS goal_trees(
        id INTEGER PRIMARY KEY, title TEXT, source TEXT, created REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS objectives(
        id INTEGER PRIMARY KEY, gid INTEGER, title TEXT, pos INTEGER)""")
    db.execute("""CREATE TABLE IF NOT EXISTS projects(
        id INTEGER PRIMARY KEY, oid INTEGER, title TEXT, pos INTEGER)""")
    db.execute("""CREATE TABLE IF NOT EXISTS gtasks(
        id INTEGER PRIMARY KEY, pid INTEGER, title TEXT, kind TEXT,
        status TEXT DEFAULT 'todo', result TEXT DEFAULT '', pos INTEGER)""")
    db.execute("""CREATE TABLE IF NOT EXISTS subtasks(
        id INTEGER PRIMARY KEY, tid INTEGER, title TEXT,
        status TEXT DEFAULT 'todo', result TEXT DEFAULT '', pos INTEGER)""")
    return db


def _insert_tree(db, title, source, spec):
    cur = db.execute("INSERT INTO goal_trees(title, source, created) VALUES(?,?,?)",
                     (title, source, time.time()))
    gid = cur.lastrowid
    for oi, o in enumerate(spec.get("objectives", [])):
        oc = db.execute("INSERT INTO objectives(gid, title, pos) VALUES(?,?,?)", (gid, o["title"], oi))
        oid = oc.lastrowid
        for pi, p in enumerate(o.get("projects", [])):
            pc = db.execute("INSERT INTO projects(oid, title, pos) VALUES(?,?,?)", (oid, p["title"], pi))
            pid = pc.lastrowid
            for ti, t in enumerate(p.get("tasks", [])):
                kind = t.get("kind", "research") if isinstance(t, dict) else "research"
                name = t.get("title", t) if isinstance(t, dict) else t
                if kind not in KINDS:
                    kind = "research"
                tc = db.execute("INSERT INTO gtasks(pid, title, kind, pos) VALUES(?,?,?,?)",
                                (pid, name, kind, ti))
                tid = tc.lastrowid
                # subtasks: only for multi-step/outside-world tasks, max 6, atomic actions stay flat
                subs = t.get("subtasks", []) if isinstance(t, dict) else []
                for si, s in enumerate(subs[:6]):
                    stitle = s.get("title", s) if isinstance(s, dict) else s
                    if str(stitle).strip():
                        db.execute("INSERT INTO subtasks(tid, title, pos) VALUES(?,?,?)",
                                   (tid, str(stitle).strip()[:300], si))
    db.commit()
    return gid


def create_from_template(key: str, title: str = ""):
    spec = TEMPLATES.get(key)
    if not spec:
        return {"ok": False, "error": "unknown template"}
    db = _db()
    gid = _insert_tree(db, title or spec["title"], f"template:{key}", spec)
    return {"ok": True, "id": gid}


def create_from_spec(title: str, spec: dict):
    db = _db()
    gid = _insert_tree(db, title, "llm", spec)
    return {"ok": True, "id": gid}


def compile_goal(title: str):
    """LLM compiles any goal into the 4-level tree. Falls back to a research outline."""
    try:
        from app.grok_client import chat_with_grok
    except ImportError:
        from grok_client import chat_with_grok
    prompt = ("Decompose this goal into JSON ONLY, no other text. Shape: "
              '{"objectives": [{"title": "...", "projects": [{"title": "...", "tasks": '
              '[{"title": "...", "kind": "research|create|browse|approval|human|wait", '
              '"subtasks": ["..."]}]}]}]}. '
              "5 or fewer objectives, 2-4 tasks per project. "
              "RULE: give a task 2-6 subtasks ONLY if it needs more than one step or touches "
              "the outside world (calendar, email, browser, people, payments). "
              "Atomic single actions (open a site, look something up) get NO subtasks. "
              f"Goal: {title}")
    import json as _j
    try:
        raw = chat_with_grok(prompt)
        s, e = raw.find("{"), raw.rfind("}")
        spec = _j.loads(raw[s:e + 1])
        if "objectives" not in spec:
            raise ValueError("no objectives")
    except Exception:
        spec = {"objectives": [{"title": "Understand + deliver",
                                "projects": [{"title": "Work", "tasks": [
                                    {"title": title, "kind": "research"}]}]}]}
    db = _db()
    gid = _insert_tree(db, title, "llm", spec)
    return {"ok": True, "id": gid}


def get_tree(gid: int):
    db = _db()
    g = db.execute("SELECT id, title, source FROM goal_trees WHERE id=?", (gid,)).fetchone()
    if not g:
        return None
    out = {"id": g[0], "title": g[1], "source": g[2], "objectives": [], "progress": 0}
    nt = nd = 0
    for oid, title in db.execute("SELECT id, title FROM objectives WHERE gid=? ORDER BY pos", (gid,)):
        o = {"id": oid, "title": title, "projects": [], "done": 0, "total": 0}
        for pid, pt in db.execute("SELECT id, title FROM projects WHERE oid=? ORDER BY pos", (oid,)):
            p = {"id": pid, "title": pt, "tasks": []}
            for tid, tt, kind, st, res in db.execute(
                    "SELECT id, title, kind, status, result FROM gtasks WHERE pid=? ORDER BY pos", (pid,)):
                subs = [{"id": s[0], "title": s[1], "status": s[2], "result": (s[3] or "")[:300]}
                        for s in db.execute(
                            "SELECT id, title, status, result FROM subtasks WHERE tid=? ORDER BY pos", (tid,))]
                p["tasks"].append({"id": tid, "title": tt, "kind": kind, "status": st,
                                   "result": res[:300], "subtasks": subs})
                o["total"] += 1
                nt += 1
                if st == "done":
                    o["done"] += 1
                    nd += 1
            o["projects"].append(p)
        out["objectives"].append(o)
    out["progress"] = round(100 * nd / max(1, nt))
    return out


def list_trees():
    db = _db()
    out = []
    for gid, title, source in db.execute("SELECT id, title, source FROM goal_trees ORDER BY id DESC"):
        tot = db.execute("SELECT COUNT(*) FROM gtasks WHERE pid IN (SELECT id FROM projects WHERE oid IN (SELECT id FROM objectives WHERE gid=?))", (gid,)).fetchone()[0]
        done = db.execute("SELECT COUNT(*) FROM gtasks WHERE status='done' AND pid IN (SELECT id FROM projects WHERE oid IN (SELECT id FROM objectives WHERE gid=?))", (gid,)).fetchone()[0]
        out.append({"id": gid, "title": title, "source": source, "total": tot, "done": done,
                    "progress": round(100 * done / max(1, tot))})
    return out


def set_task(tid: int, status: str, result: str = ""):
    db = _db()
    db.execute("UPDATE gtasks SET status=?, result=? WHERE id=?", (status, result[:2000], tid))
    db.commit()
    return {"ok": True}


def set_subtask(sid: int, status: str, result: str = ""):
    db = _db()
    db.execute("UPDATE subtasks SET status=?, result=? WHERE id=?", (status, result[:2000], sid))
    db.commit()
    return {"ok": True}


def list_subtasks(tid: int):
    db = _db()
    rows = db.execute("SELECT id, title, status, result FROM subtasks WHERE tid=? ORDER BY pos", (tid,)).fetchall()
    return [{"id": r[0], "title": r[1], "status": r[2], "result": (r[3] or "")[:300]} for r in rows]


def run_task(tid: int, device: str = "api"):
    """Execute one leaf by kind. research/create/browse -> agent loop;
    approval -> approval record; human -> open loop; wait -> watched goal."""
    db = _db()
    r = db.execute("SELECT title, kind FROM gtasks WHERE id=?", (tid,)).fetchone()
    if not r:
        return {"ok": False, "error": "task not found"}
    title, kind = r
    set_task(tid, "doing")
    try:
        if kind in ("research", "create", "browse"):
            try:
                from app.agent import run_goal
            except ImportError:
                from agent import run_goal
            result = run_goal(f"{title} (goal-tree task, be concrete, save files to workspace)")
            set_task(tid, "done", result)
            return {"ok": True, "status": "done", "result": result[:500]}
        if kind == "approval":
            try:
                from app.memory import Memory
            except ImportError:
                from memory import Memory
            aid = Memory().approval_create(title, device, "task", "")
            set_task(tid, "waiting", f"approval #{aid}")
            return {"ok": True, "status": "waiting", "approval_id": aid}
        if kind == "human":
            try:
                from app.loops import add as ladd
            except ImportError:
                from loops import add as ladd
            lr = ladd("promise", title, device)
            set_task(tid, "waiting", f"loop #{lr['id']}")
            return {"ok": True, "status": "waiting", "loop_id": lr["id"]}
        # wait
        try:
            from app.goals import create as gcreate
        except ImportError:
            from goals import create as gcreate
        gr = gcreate(title, "", "checklist")
        set_task(tid, "waiting", "watch created")
        return {"ok": True, "status": "waiting"}
    except Exception as e:
        set_task(tid, "failed", str(e)[:300])
        return {"ok": False, "error": str(e)[:300]}
