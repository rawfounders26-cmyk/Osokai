"""Fill queue — agent requests field fills, extension executes after policy gate.
CAPTCHA handoff: needs-human tasks notify everywhere (extension popup, mobile bell,
desktop corner bell); user solves, marks solved, flow resumes."""
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

def _db():
    db = _hardb(os.path.normpath(DB))
    db.execute("""CREATE TABLE IF NOT EXISTS fill_requests(
        id INTEGER PRIMARY KEY, site TEXT, fields TEXT, status TEXT,
        otp TEXT DEFAULT '', created REAL, updated REAL)""")
    return db

def request_fill(site: str, fields: str = "login"):
    """fields: comma list among username,password,totp,number,expiry,cvv,name."""
    db = _db()
    cur = db.execute("INSERT INTO fill_requests(site, fields, status, created, updated) VALUES(?,?,?,?,?)",
                     (site, fields, "pending", time.time(), time.time()))
    db.commit()
    return {"ok": True, "id": cur.lastrowid}

def pending_for(domain: str):
    db = _db()
    rows = db.execute("SELECT id, site, fields, status FROM fill_requests "
                      "WHERE status IN ('pending','captcha') ORDER BY id DESC LIMIT 10").fetchall()
    out = []
    for i, site, fields, st in rows:
        if domain and site and domain != site and site not in domain and domain not in site:
            continue
        r = {"id": i, "site": site, "fields": fields, "status": st}
        if st == "pending":
            otp = db.execute("SELECT otp FROM fill_requests WHERE id=?", (i,)).fetchone()
            if otp and otp[0]:
                r["otp"] = otp[0]
        out.append(r)
    return out

def mark(id_: int, status: str):
    db = _db()
    db.execute("UPDATE fill_requests SET status=?, updated=? WHERE id=?", (status, time.time(), id_))
    db.commit()
    return {"ok": True, "id": id_, "status": status}

def set_otp(code: str):
    """User-pasted OTP goes to the newest fill awaiting one. Encrypted at rest, burned on use."""
    db = _db()
    try:
        from app.vault import encrypt, decrypt
    except ImportError:
        from vault import encrypt, decrypt
    row = db.execute("SELECT id FROM fill_requests WHERE status='pending' ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return {}
    db.execute("UPDATE fill_requests SET otp=?, updated=? WHERE id=?", (encrypt(code), time.time(), row[0]))
    db.commit()
    return {"id": row[0]}

def take_otp(id_: int):
    """Extension pulls + burns the OTP (single use)."""
    db = _db()
    try:
        from app.vault import decrypt
    except ImportError:
        from vault import decrypt
    row = db.execute("SELECT otp FROM fill_requests WHERE id=?", (id_,)).fetchone()
    if not row or not row[0]:
        return ""
    db.execute("UPDATE fill_requests SET otp='', updated=? WHERE id=?", (time.time(), id_))
    db.commit()
    try:
        return decrypt(row[0])
    except Exception:
        return ""

def captcha_count():
    db = _db()
    try:
        return db.execute("SELECT COUNT(*) FROM fill_requests WHERE status='captcha'").fetchone()[0]
    except Exception:
        return 0
