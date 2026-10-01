"""Local memory mirror — SQLite cache + workspace files. Supabase is source of truth when configured."""
import calendar
import datetime
import os, sqlite3, time

try:
    from app.paths import data as _pdata, ws as _pws
except ImportError:
    from paths import data as _pdata, ws as _pws

try:
    from app.db import connect as _hardb
except ImportError:
    from db import connect as _hardb
DB = _pdata("osokai.db")
WS = _pws()

# single shared connection + scheduler/proactive/chat threads -> guard all writes
import threading as _th
_lock = _th.RLock()

class Memory:
    def __init__(self):
        os.makedirs(WS, exist_ok=True)
        self.db = _hardb(os.path.normpath(DB))
        self.db.execute("CREATE TABLE IF NOT EXISTS turns(role TEXT, text TEXT, ts REAL)")
        self.db.execute("""CREATE TABLE IF NOT EXISTS approvals(
            id INTEGER PRIMARY KEY, message TEXT, device TEXT, status TEXT,
            kind TEXT, item TEXT, ts REAL, reply TEXT)""")
        # Memory 2.0: episodic facts with salience + rolling summary
        self.db.execute("""CREATE TABLE IF NOT EXISTS facts(
            id INTEGER PRIMARY KEY, fact TEXT, salience REAL DEFAULT 1.0, ts REAL)""")
        self.db.execute("CREATE TABLE IF NOT EXISTS summary(id INTEGER PRIMARY KEY CHECK(id=1), text TEXT, updated REAL)")

    def add(self, role, text):
        with _lock:
            self.db.execute("INSERT INTO turns VALUES(?,?,?)", (role, text, time.time()))
            self.db.commit()
        try:
            n = self.db.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
            if n % 50 == 0:
                self._refresh_summary()
        except Exception:
            pass

    # ---- episodic memory: durable facts, salience-ranked recall ----
    def note_fact(self, fact: str, salience: float = 1.0):
        with _lock:
            cur = self.db.execute("INSERT INTO facts(fact, salience, ts) VALUES(?,?,?)",
                                  (fact[:1000], max(0.1, min(5.0, salience)), time.time()))
            self.db.commit()
            return cur.lastrowid

    def recall(self, query: str = "", k: int = 5):
        terms = [t for t in query.lower().split() if len(t) > 2]
        rows = self.db.execute("SELECT id, fact, salience, ts FROM facts ORDER BY salience DESC, ts DESC LIMIT 50").fetchall()
        scored = []
        for r in rows:
            fl = r[1].lower()
            s = r[2] + sum(1.0 for t in terms if t in fl)
            if not terms or any(t in fl for t in terms):
                scored.append((s, {"id": r[0], "fact": r[1], "salience": r[2], "ts": r[3]}))
        scored.sort(key=lambda s: -s[0])
        return [s[1] for s in scored[:k]]

    def get_summary(self) -> str:
        try:
            r = self.db.execute("SELECT text FROM summary WHERE id=1").fetchone()
            return r[0] if r else ""
        except Exception:
            return ""

    # ---- memory package: people / places / unified recall (façade delegates) ----
    # top-level first (tests), app.* fallback (server): same copy per environment
    def remember_person(self, name: str, relation: str = "", notes: str = ""):
        try:
            from memory.people import remember_person
        except ImportError:
            from app.memory.people import remember_person
        return remember_person(name, relation, notes)

    def remember_place(self, name: str, kind: str = "", notes: str = ""):
        try:
            from memory.places import remember_place
        except ImportError:
            from app.memory.places import remember_place
        return remember_place(name, kind, notes)

    def recall_all(self, query: str = "", k: int = 8):
        try:
            from memory.retrieval import recall_all
        except ImportError:
            from app.memory.retrieval import recall_all
        return recall_all(query, k)

    def consolidate(self):
        try:
            from memory.consolidation import run
        except ImportError:
            from app.memory.consolidation import run
        return run()

    def _refresh_summary(self):
        rows = self.db.execute("SELECT role, text FROM turns ORDER BY ts DESC LIMIT 30").fetchall()
        convo = "\n".join(f"{r[0]}: {r[1][:300]}" for r in reversed(rows))
        text = ""
        try:
            try:
                from app.grok_client import chat_with_grok
            except ImportError:
                from grok_client import chat_with_grok
            text = chat_with_grok("Summarize this user-agent conversation in 5 bullet facts "
                                  "(preferences, names, ongoing goals). No fluff:\n" + convo)[:2000]
        except Exception:
            pass
        if not text:
            users = [r[1][:160] for r in rows if r[0] == "user"][:5]
            text = "Recent threads: " + " | ".join(users)
        with _lock:
            self.db.execute("INSERT OR REPLACE INTO summary(id, text, updated) VALUES(1,?,?)", (text, time.time()))
            self.db.commit()

    # ---- durable approvals: survive backend restarts (unlike in-memory dicts) ----
    def approval_create(self, message, device, kind="general", item=""):
        with _lock:
            cur = self.db.execute(
                "INSERT INTO approvals(message, device, status, kind, item, ts, reply) VALUES(?,?,?,?,?,?,?)",
                (message, device, "pending", kind, item, time.time(), ""))
            self.db.commit()
            aid = cur.lastrowid
        try:
            from app.context.normalizers import approval_requested
        except ImportError:
            try:
                from context.normalizers import approval_requested
            except ImportError:
                approval_requested = lambda *a: None
        try:
            approval_requested(aid, message)
        except Exception:
            pass
        return aid

    def approval_get(self, aid):
        r = self.db.execute("SELECT id, message, device, status, kind, item, ts, reply FROM approvals WHERE id=?",
                            (aid,)).fetchone()
        return self._arow(r) if r else None

    def approval_list_pending(self):
        rows = self.db.execute("SELECT id, message, device, status, kind, item, ts, reply FROM approvals WHERE status='pending' ORDER BY id").fetchall()
        return [self._arow(r) for r in rows]

    def approval_resolve(self, aid, allow, reply):
        with _lock:
            self.db.execute("UPDATE approvals SET status=?, reply=? WHERE id=? AND status='pending'",
                            ("allowed" if allow else "denied", reply, aid))
            self.db.commit()
        try:
            from app.context.normalizers import approval_resolved
        except ImportError:
            try:
                from context.normalizers import approval_resolved
            except ImportError:
                approval_resolved = lambda *a: None
        try:
            approval_resolved(aid, "allowed" if allow else "denied")
        except Exception:
            pass
        return self.approval_get(aid)

    @staticmethod
    def _arow(r):
        return {"id": r[0], "message": r[1], "device": r[2], "status": r[3],
                "kind": r[4], "item": r[5], "ts": r[6], "reply": r[7]}

    def tasks_running(self):
        return []

    def tasks_previous(self):
        rows = self.db.execute("SELECT role, text, ts FROM turns ORDER BY ts DESC LIMIT 20").fetchall()
        return [{"role": r[0], "text": r[1][:200], "ts": r[2]} for r in rows]

    def month_key(self, ts=None):
        d = datetime.datetime.fromtimestamp(ts or time.time())
        return d.strftime("%Y-%m"), d.strftime("%b-%y")

    def month_days(self, ym: str):
        """Per-day user-goal counts for one YYYY-MM (drives the usage graph)."""
        try:
            y, m = int(ym.split("-")[0]), int(ym.split("-")[1])
            ndays = calendar.monthrange(y, m)[1]
        except Exception:
            return []
        out = []
        for d in range(1, ndays + 1):
            lo = datetime.datetime(y, m, d).timestamp()
            n = self.db.execute(
                "SELECT COUNT(*) FROM turns WHERE role='user' AND ts>=? AND ts<?", (lo, lo + 86400)).fetchone()[0]
            out.append({"date": f"{ym}-{d:02d}", "day": d, "total": n})
        return out

    def month_detail(self, ym: str):
        """Tasks/goals + usage for one YYYY-MM bucket. Goals = user turns."""
        try:
            y, m = ym.split("-")
            lo = datetime.datetime(int(y), int(m), 1).timestamp()
            hi = datetime.datetime(int(y) + (int(m) == 12), int(m) % 12 + 1, 1).timestamp()
        except Exception:
            return {"month": ym, "label": ym, "tasks": 0, "usage": "0 tasks", "goals": []}
        rows = self.db.execute(
            "SELECT role, text, ts FROM turns WHERE ts>=? AND ts<? ORDER BY ts DESC", (lo, hi)).fetchall()
        goals = [{"text": r[1][:200], "ts": r[2]} for r in rows if r[0] == "user"]
        # past goal-trees belong to their month folder too
        try:
            grows = self.db.execute(
                "SELECT id, title, created FROM goal_trees WHERE created>=? AND created<? ORDER BY created DESC",
                (lo, hi)).fetchall()
        except Exception:
            grows = []
        for gid, title, ts in grows:
            goals.append({"text": f"🎯 Goal: {title}", "ts": ts, "goal_id": gid})
        goals.sort(key=lambda g: g["ts"], reverse=True)
        label = datetime.datetime(int(y), int(m), 1).strftime("%b-%y")
        return {"month": ym, "label": label, "tasks": len(goals),
                "usage": f"{len(goals)} goals · {len(rows)} exchanges",
                "goals": goals[:50]}

    def months_flow(self, past=3, future=2):
        """Past + current + upcoming months auto-generated from time flow."""
        now = datetime.datetime.now()
        out = []
        for off in range(-past, future + 1):
            m = (now.month - 1 + off) % 12 + 1
            y = now.year + (now.month - 1 + off) // 12
            ym = f"{y:04d}-{m:02d}"
            d = self.month_detail(ym)
            d["current"] = (off == 0)
            d["upcoming"] = (off > 0)
            out.append(d)
        # daily buckets (last 7 days) for the weekly chart
        days = []
        for i in range(6, -1, -1):
            day = now - datetime.timedelta(days=i)
            lo = day.replace(hour=0, minute=0, second=0).timestamp()
            hi = lo + 86400
            n = self.db.execute("SELECT COUNT(*) FROM turns WHERE role='user' AND ts>=? AND ts<?", (lo, hi)).fetchone()[0]
            days.append({"day": day.strftime("%a"), "tasks": n})
        total = sum(m["tasks"] for m in out if not m["upcoming"])
        best = max(days, key=lambda d: d["tasks"]) if days else {"day": "-", "tasks": 0}
        return {"months": out, "week": days,
                "total_tasks": total, "best_day": best}

    def list_files(self, sub: str = ""):
        try:
            try:
                from app.paths import safe_join as _sj
            except ImportError:
                from paths import safe_join as _sj
            return sorted(os.listdir(_sj(sub)))
        except Exception:
            return []

    def list_entries(self, sub: str = ""):
        try:
            try:
                from app.paths import safe_join as _sj
            except ImportError:
                from paths import safe_join as _sj
            base = _sj(sub)
            out = []
            for n in sorted(os.listdir(base)):
                out.append({"name": n, "dir": os.path.isdir(os.path.join(base, n))})
            return out
        except Exception:
            return []
