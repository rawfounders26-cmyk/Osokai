"""Local memory mirror — SQLite cache + workspace files. Supabase is source of truth when configured."""
import calendar
import datetime
import os, sqlite3, time

DB = os.path.join(os.path.dirname(__file__), "..", "osokai.db")
WS = os.path.join(os.path.dirname(__file__), "..", "..", "workspace")

class Memory:
    def __init__(self):
        os.makedirs(WS, exist_ok=True)
        self.db = sqlite3.connect(os.path.normpath(DB), check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS turns(role TEXT, text TEXT, ts REAL)")
        self.db.execute("""CREATE TABLE IF NOT EXISTS approvals(
            id INTEGER PRIMARY KEY, message TEXT, device TEXT, status TEXT,
            kind TEXT, item TEXT, ts REAL, reply TEXT)""")

    def add(self, role, text):
        self.db.execute("INSERT INTO turns VALUES(?,?,?)", (role, text, time.time()))
        self.db.commit()

    # ---- durable approvals: survive backend restarts (unlike in-memory dicts) ----
    def approval_create(self, message, device, kind="general", item=""):
        cur = self.db.execute(
            "INSERT INTO approvals(message, device, status, kind, item, ts, reply) VALUES(?,?,?,?,?,?,?)",
            (message, device, "pending", kind, item, time.time(), ""))
        self.db.commit()
        return cur.lastrowid

    def approval_get(self, aid):
        r = self.db.execute("SELECT id, message, device, status, kind, item, ts, reply FROM approvals WHERE id=?",
                            (aid,)).fetchone()
        return self._arow(r) if r else None

    def approval_list_pending(self):
        rows = self.db.execute("SELECT id, message, device, status, kind, item, ts, reply FROM approvals WHERE status='pending' ORDER BY id").fetchall()
        return [self._arow(r) for r in rows]

    def approval_resolve(self, aid, allow, reply):
        self.db.execute("UPDATE approvals SET status=?, reply=? WHERE id=? AND status='pending'",
                        ("allowed" if allow else "denied", reply, aid))
        self.db.commit()
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
            base = os.path.normpath(os.path.join(WS, sub))
            if not base.startswith(WS):
                return []
            return sorted(os.listdir(base))
        except Exception:
            return []

    def list_entries(self, sub: str = ""):
        try:
            base = os.path.normpath(os.path.join(WS, sub))
            if not base.startswith(WS):
                return []
            out = []
            for n in sorted(os.listdir(base)):
                out.append({"name": n, "dir": os.path.isdir(os.path.join(base, n))})
            return out
        except Exception:
            return []
