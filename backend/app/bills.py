"""Bills — shared expenses tracker for friends & groups.
Tables live in osokai.db next to memory turns. Math in code, never LLM."""
import sqlite3, time, os

try:
    from app.paths import data as _pdata
except ImportError:
    from paths import data as _pdata

try:
    from app.db import connect as _hardb
except ImportError:
    from db import connect as _hardb
DB = _pdata("osokai.db")

def _db():
    db = _hardb(os.path.normpath(DB))
    db.execute("CREATE TABLE IF NOT EXISTS bill_groups(id INTEGER PRIMARY KEY, name TEXT, created REAL)")
    db.execute("CREATE TABLE IF NOT EXISTS bill_members(id INTEGER PRIMARY KEY, gid INTEGER, name TEXT)")
    try:
        db.execute("ALTER TABLE bill_members ADD COLUMN upi TEXT DEFAULT ''")
    except Exception:
        pass
    db.execute("CREATE TABLE IF NOT EXISTS bill_expenses(id INTEGER PRIMARY KEY, gid INTEGER, title TEXT, amount REAL, paid_by TEXT, ts REAL)")
    db.execute("CREATE TABLE IF NOT EXISTS bill_splits(id INTEGER PRIMARY KEY, eid INTEGER, who TEXT, share REAL)")
    db.execute("CREATE TABLE IF NOT EXISTS bill_settle(id INTEGER PRIMARY KEY, gid INTEGER, frm TEXT, recipient TEXT, amount REAL, ts REAL)")
    db.execute("""CREATE TABLE IF NOT EXISTS bill_recurring(
        id INTEGER PRIMARY KEY, gid INTEGER, title TEXT, amount REAL, paid_by TEXT,
        splits TEXT DEFAULT '', day INT DEFAULT 1, last_post TEXT DEFAULT '')""")
    db.execute("CREATE TABLE IF NOT EXISTS team_bill_link(gid INTEGER PRIMARY KEY, team INTEGER)")
    return db

def create_group(name: str, members):
    db = _db()
    cur = db.execute("INSERT INTO bill_groups(name, created) VALUES(?,?)", (name, time.time()))
    gid = cur.lastrowid
    for m in (members or []):
        m = str(m).strip()
        if m:
            db.execute("INSERT INTO bill_members(gid, name) VALUES(?,?)", (gid, m))
    db.commit()
    return {"ok": True, "id": gid, "name": name}

def list_groups():
    db = _db()
    out = []
    for gid, name, created in db.execute("SELECT id, name, created FROM bill_groups ORDER BY id DESC"):
        mems = [r[0] for r in db.execute("SELECT name FROM bill_members WHERE gid=?", (gid,))]
        out.append({"id": gid, "name": name, "members": mems, "created": created,
                    "balances": balances(gid)["debts"]})
    return out

def add_expense(gid: int, title: str, amount: float, paid_by: str, splits: dict):
    """splits: {who: share}. Empty/None => equal across group members."""
    db = _db()
    g = db.execute("SELECT id FROM bill_groups WHERE id=?", (gid,)).fetchone()
    if not g:
        return {"ok": False, "error": "group not found"}
    mems = [r[0] for r in db.execute("SELECT name FROM bill_members WHERE gid=?", (gid,))]
    if not splits:
        if not mems:
            return {"ok": False, "error": "no members in group"}
        share = round(float(amount) / len(mems), 2)
        splits = {m: share for m in mems}
    cur = db.execute("INSERT INTO bill_expenses(gid, title, amount, paid_by, ts) VALUES(?,?,?,?,?)",
                     (gid, title, float(amount), paid_by, time.time()))
    eid = cur.lastrowid
    for who, share in splits.items():
        db.execute("INSERT INTO bill_splits(eid, who, share) VALUES(?,?,?)", (eid, who, float(share)))
    db.commit()
    try:
        from app.context.normalizers import expense_added
    except ImportError:
        try:
            from context.normalizers import expense_added
        except ImportError:
            expense_added = lambda *a: None
    try:
        expense_added(eid, title, float(amount))
    except Exception:
        pass
    return {"ok": True, "id": eid}

def balances(gid: int):
    """Net per person + simplified debts (who pays who)."""
    db = _db()
    net = {}
    for eid, title, amount, paid_by in db.execute("SELECT id, title, amount, paid_by FROM bill_expenses WHERE gid=?", (gid,)):
        net[paid_by] = net.get(paid_by, 0) + float(amount)
        for who, share in db.execute("SELECT who, share FROM bill_splits WHERE eid=?", (eid,)):
            net[who] = net.get(who, 0) - float(share)
    for sid, frm, recipient, amount in db.execute("SELECT id, frm, recipient, amount FROM bill_settle WHERE gid=?", (gid,)):
        net[frm] = net.get(frm, 0) + float(amount)
        net[recipient] = net.get(recipient, 0) - float(amount)
    net = {k: round(v, 2) for k, v in net.items() if abs(v) > 0.005}
    # greedy simplify
    creditors = sorted([(k, v) for k, v in net.items() if v > 0], key=lambda x: -x[1])
    debtors = sorted([(k, -v) for k, v in net.items() if v < 0], key=lambda x: -x[1])
    debts = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        dk, da = debtors[i]
        ck, ca = creditors[j]
        x = round(min(da, ca), 2)
        debts.append({"from": dk, "to": ck, "amount": x})
        debtors[i] = (dk, round(da - x, 2))
        creditors[j] = (ck, round(ca - x, 2))
        if debtors[i][1] <= 0.005:
            i += 1
        if creditors[j][1] <= 0.005:
            j += 1
    return {"net": net, "debts": debts}

def settle(gid: int, frm: str, to: str, amount: float):
    db = _db()
    # idempotent: exact same settlement within 60s returns the original (no double-pay)
    dup = db.execute("SELECT id FROM bill_settle WHERE gid=? AND frm=? AND recipient=? AND amount=? AND ts>?",
                     (gid, frm, to, float(amount), time.time() - 60)).fetchone()
    if dup:
        return {"ok": True, "id": dup[0], "duplicate": True}
    cur = db.execute("INSERT INTO bill_settle(gid, frm, recipient, amount, ts) VALUES(?,?,?,?,?)",
                     (gid, frm, to, float(amount), time.time()))
    db.commit()
    return {"ok": True, "id": cur.lastrowid}


def verify_ledger(gid: int) -> dict:
    """Money invariants: splits cover each expense, debts net to ~zero, no negatives."""
    db = _db()
    errors = []
    for eid, title, amount in db.execute("SELECT id, title, amount FROM bill_expenses WHERE gid=?", (gid,)):
        if amount < 0:
            errors.append(f"negative expense #{eid} ({title})")
            continue
        s = db.execute("SELECT SUM(share) FROM bill_splits WHERE eid=?", (eid,)).fetchone()[0] or 0
        if abs(s - amount) > 0.05:
            errors.append(f"expense #{eid} ({title}): splits ₹{s} ≠ ₹{amount}")
        for who, share in db.execute("SELECT who, share FROM bill_splits WHERE eid=?", (eid,)):
            if share < 0:
                errors.append(f"negative split #{eid} for {who}")
    b = balances(gid)
    net = round(sum(b["net"].values()), 2)
    if abs(net) > 0.05:
        errors.append(f"net imbalance ₹{net} (must net to zero)")
    for d in b["debts"]:
        if d["amount"] <= 0:
            errors.append(f"non-positive debt {d}")
    return {"ok": not errors, "errors": errors, "debts": len(b["debts"])}

def activity(gid: int, limit: int = 30):
    db = _db()
    rows = db.execute("SELECT title, amount, paid_by, ts FROM bill_expenses WHERE gid=? ORDER BY ts DESC LIMIT ?",
                      (gid, limit)).fetchall()
    out = [{"title": r[0], "amount": r[1], "paid_by": r[2], "ts": r[3]} for r in rows]
    st = db.execute("SELECT frm, recipient, amount, ts FROM bill_settle WHERE gid=? ORDER BY ts DESC LIMIT ?",
                    (gid, limit)).fetchall()
    out += [{"settle": True, "frm": r[0], "to": r[1], "amount": r[2], "ts": r[3]} for r in st]
    return sorted(out, key=lambda x: x["ts"], reverse=True)


def find_group(name: str):
    """Fuzzy group lookup by name for chat ('flat' matches 'Flat mates')."""
    name = (name or "").strip().lower()
    if not name:
        return None
    groups = list_groups()
    for g in groups:
        if g["name"].lower() == name:
            return g
    for g in groups:
        if name in g["name"].lower() or g["name"].lower() in name:
            return g
    return None


def members(gid: int):
    db = _db()
    try:
        rows = db.execute("SELECT name, upi FROM bill_members WHERE gid=?", (gid,)).fetchall()
        return [{"name": r[0], "upi": r[1] or ""} for r in rows]
    except Exception:
        return [{"name": r[0], "upi": ""} for r in db.execute("SELECT name FROM bill_members WHERE gid=?", (gid,))]


def set_upi(gid: int, name: str, upi: str) -> dict:
    db = _db()
    db.execute("UPDATE bill_members SET upi=? WHERE gid=? AND name=?", (upi.strip(), gid, name))
    db.commit()
    return {"ok": True}


def upi_link(pa: str, pn: str, amount: float, note: str = "") -> str:
    import urllib.parse as _u
    q = _u.urlencode({"pa": pa, "pn": pn, "am": f"{amount:.2f}", "cu": "INR", "tn": note[:80]})
    return f"upi://pay?{q}"


def settle_up(gid: int) -> dict:
    """Debts + one-tap UPI links where the creditor registered one. Splitwise can't do this."""
    b = balances(gid)
    upis = {m["name"]: m["upi"] for m in members(gid)}
    debts = []
    for d in b["debts"]:
        upi = upis.get(d["to"], "")
        link = upi_link(upi, d["to"], d["amount"], "OsokAI split") if upi else ""
        debts.append({**d, "upi": link})
    if not debts:
        return {"ok": True, "debts": [], "reply": "All settled — nothing owed."}
    lines = [f"• {d['from']} → {d['to']}: ₹{d['amount']}" + (" (tap to pay ⬆)" if d["upi"] else " (no UPI id — ask them to set one)") for d in debts]
    return {"ok": True, "debts": debts, "reply": "Settle up:\n" + "\n".join(lines)}


def add_recurring(gid: int, title: str, amount: float, paid_by: str = "Me", splits: dict = None, day: int = 1) -> dict:
    import json as _j
    db = _db()
    if not db.execute("SELECT 1 FROM bill_groups WHERE id=?", (gid,)).fetchone():
        return {"ok": False, "error": "group not found"}
    cur = db.execute("INSERT INTO bill_recurring(gid, title, amount, paid_by, splits, day) VALUES(?,?,?,?,?,?)",
                     (gid, title, float(amount), paid_by, _j.dumps(splits or {}), max(1, min(28, day))))
    db.commit()
    return {"ok": True, "id": cur.lastrowid}


def list_recurring(gid: int = 0):
    import json as _j
    db = _db()
    q = "SELECT id, gid, title, amount, paid_by, splits, day, last_post FROM bill_recurring"
    args: tuple = ()
    if gid:
        q += " WHERE gid=?"
        args = (gid,)
    out = []
    for r in db.execute(q, args).fetchall():
        try:
            sp = _j.loads(r[5] or "{}")
        except Exception:
            sp = {}
        out.append({"id": r[0], "gid": r[1], "title": r[2], "amount": r[3], "paid_by": r[4],
                    "splits": sp, "day": r[6], "last_post": r[7]})
    return out


def post_due_recurring() -> dict:
    """Post this month's recurring expenses whose day has come. Scheduler calls this."""
    import datetime as _dt
    today = _dt.date.today()
    posted = []
    for r in list_recurring():
        if today.day >= r["day"] and r["last_post"] != today.strftime("%Y-%m"):
            e = add_expense(r["gid"], f"{r['title']} ({today.strftime('%b %Y')})",
                            r["amount"], r["paid_by"], r["splits"])
            if e.get("ok"):
                _dbm = _db()
                _dbm.execute("UPDATE bill_recurring SET last_post=? WHERE id=?",
                             (today.strftime("%Y-%m"), r["id"]))
                _dbm.commit()
                posted.append(r["title"])
    return {"ok": True, "posted": posted}


def link_team(gid: int, tid: int) -> dict:
    db = _db()
    db.execute("INSERT OR REPLACE INTO team_bill_link(gid, team) VALUES(?,?)", (gid, tid))
    db.commit()
    return {"ok": True}


def team_groups(tid: int):
    db = _db()
    gids = [r[0] for r in db.execute("SELECT gid FROM team_bill_link WHERE team=?", (tid,))]
    return [g for g in list_groups() if g["id"] in gids]


def house_ledger(gid: int, ym: str = "") -> dict:
    """Monthly household ledger: totals, who paid, who owes."""
    import datetime as _dt
    if not ym:
        ym = _dt.date.today().strftime("%Y-%m")
    try:
        y, m = int(ym[:4]), int(ym[5:7])
        lo = _dt.datetime(y, m, 1).timestamp()
        hi = _dt.datetime(y + (m == 12), m % 12 + 1, 1).timestamp()
    except Exception:
        return {"ok": False, "error": "bad month"}
    db = _db()
    rows = db.execute("SELECT title, amount, paid_by FROM bill_expenses WHERE gid=? AND ts>=? AND ts<?",
                      (gid, lo, hi)).fetchall()
    total = round(sum(r[1] for r in rows), 2)
    paid = {}
    for t, a, p in rows:
        paid[p] = round(paid.get(p, 0) + a, 2)
    b = balances(gid)
    g = db.execute("SELECT name FROM bill_groups WHERE id=?", (gid,)).fetchone()
    name = g[0] if g else f"group {gid}"
    lines = [f"{name} — {ym}: ₹{total} across {len(rows)} expense(s).",
             "Paid: " + (", ".join(f"{k} ₹{v}" for k, v in paid.items()) or "—")]
    if b["debts"]:
        lines.append("Owes: " + "; ".join(f"{d['from']} → {d['to']} ₹{d['amount']}" for d in b["debts"]))
    else:
        lines.append("All settled ✓")
    return {"ok": True, "month": ym, "total": total, "paid": paid, "debts": b["debts"],
            "reply": "\n".join(lines)}


def parse_receipt(b64_image: str) -> dict:
    """Receipt photo -> draft expense (never commits without confirm)."""
    try:
        try:
            from app.grok_client import chat_with_vision
        except ImportError:
            from grok_client import chat_with_vision
    except Exception as e:
        return {"ok": False, "error": f"vision unavailable: {e}"}
    raw = chat_with_vision(
        "Read this receipt/bill photo. JSON ONLY, no other text: "
        '{"merchant": "...", "total": 0, "items": [{"name": "...", "price": 0}]}. '
        "Numbers only for prices.", b64_image)
    if raw.startswith("[osok"):
        return {"ok": False, "error": raw}
    import json as _j
    try:
        s, e = raw.find("{"), raw.rfind("}")
        d = _j.loads(raw[s:e + 1])
        items = [{"name": str(i.get("name", "item")), "price": float(i.get("price", 0))} for i in d.get("items", [])]
        return {"ok": True, "draft": {"title": str(d.get("merchant", "Receipt"))[:120],
                                      "total": float(d.get("total", 0)), "items": items}}
    except Exception:
        return {"ok": False, "error": "Couldn't read that receipt — try flatter, better light."}

