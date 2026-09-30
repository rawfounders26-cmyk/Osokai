"""Bills — shared expenses tracker for friends & groups.
Tables live in osokai.db next to memory turns. Math in code, never LLM."""
import sqlite3, time, os

DB = os.path.join(os.path.dirname(__file__), "..", "osokai.db")

def _db():
    db = sqlite3.connect(os.path.normpath(DB), check_same_thread=False)
    db.execute("CREATE TABLE IF NOT EXISTS bill_groups(id INTEGER PRIMARY KEY, name TEXT, created REAL)")
    db.execute("CREATE TABLE IF NOT EXISTS bill_members(id INTEGER PRIMARY KEY, gid INTEGER, name TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS bill_expenses(id INTEGER PRIMARY KEY, gid INTEGER, title TEXT, amount REAL, paid_by TEXT, ts REAL)")
    db.execute("CREATE TABLE IF NOT EXISTS bill_splits(id INTEGER PRIMARY KEY, eid INTEGER, who TEXT, share REAL)")
    db.execute("CREATE TABLE IF NOT EXISTS bill_settle(id INTEGER PRIMARY KEY, gid INTEGER, frm TEXT, recipient TEXT, amount REAL, ts REAL)")
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
    db.execute("INSERT INTO bill_settle(gid, frm, recipient, amount, ts) VALUES(?,?,?,?,?)",
               (gid, frm, to, float(amount), time.time()))
    db.commit()
    return {"ok": True}

def activity(gid: int, limit: int = 30):
    db = _db()
    rows = db.execute("SELECT title, amount, paid_by, ts FROM bill_expenses WHERE gid=? ORDER BY ts DESC LIMIT ?",
                      (gid, limit)).fetchall()
    out = [{"title": r[0], "amount": r[1], "paid_by": r[2], "ts": r[3]} for r in rows]
    st = db.execute("SELECT frm, recipient, amount, ts FROM bill_settle WHERE gid=? ORDER BY ts DESC LIMIT ?",
                    (gid, limit)).fetchall()
    out += [{"settle": True, "frm": r[0], "to": r[1], "amount": r[2], "ts": r[3]} for r in st]
    return sorted(out, key=lambda x: x["ts"], reverse=True)

