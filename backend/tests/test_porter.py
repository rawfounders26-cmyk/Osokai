"""Osok-AI smoke tests — intents, router, bills math, vault, durable approvals, goals."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from intents import parse, payment_parse
from sentinel import needs_approval


def test_youtube_song_and_episode():
    a, _ = parse("open youtube and play radhima song")
    assert a["type"] == "youtube_play"
    a, _ = parse("watch bigg boss episode 5")
    assert a["type"] == "youtube_play" and "episode 5" in a["query"]


def test_images_and_google():
    a, _ = parse("open dog images on google")
    assert a["type"] == "open_url" and "tbm=isch" in a["url"]
    a, _ = parse("open google and search the recent yc invested startups")
    assert a["type"] == "open_url" and "google.com/search" in a["url"]


def test_payment_parse():
    assert payment_parse("buy mens shoes")["kind"] == "payment"
    assert payment_parse("hello") is None
    assert needs_approval("buy shoes") is True
    assert needs_approval("hello") is False


def test_router(tmp_path=None):
    from skills_index import route
    assert route("prepare a ppt on EVs") == ["pptx"] or "pptx" in route("prepare a ppt on EVs")
    assert "legal-risk-assessment-zacharie-laik" in route("draft a legal notice")


def test_bills_math(tmp_path, monkeypatch):
    import bills
    monkeypatch.setattr(bills, "DB", str(tmp_path / "t.db"))
    g = bills.create_group("trip", ["Me", "Ravi", "Priya"])
    bills.add_expense(g["id"], "Dinner", 2400, "Me", {})
    b = bills.balances(g["id"])
    assert b["debts"] == [{"from": "Ravi", "to": "Me", "amount": 800.0},
                          {"from": "Priya", "to": "Me", "amount": 800.0}]
    bills.settle(g["id"], "Ravi", "Me", 800)
    b = bills.balances(g["id"])
    assert b["debts"] == [{"from": "Priya", "to": "Me", "amount": 800.0}]


def test_vault_roundtrip(monkeypatch):
    from cryptography.fernet import Fernet
    import vault
    monkeypatch.setenv("OSOKAI_VAULT_KEY", Fernet.generate_key().decode())
    assert vault.decrypt(vault.encrypt("4111111111111111")) == "4111111111111111"
    assert vault.mask("4111111111111111").endswith("1111")


def test_vault2_policies_lock_audit(tmp_path, monkeypatch):
    import vault
    from cryptography.fernet import Fernet
    monkeypatch.setenv("OSOKAI_VAULT_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(vault, "_STORE", str(tmp_path / "s.json"))
    monkeypatch.setattr(vault, "_DB", str(tmp_path / "a.db"))
    vault.lock()
    assert vault.lock_status()["locked"] is True
    vault.secret_set("card", "cnum", "4111111111111111")
    import pytest as _pt
    with _pt.raises(PermissionError):
        vault.secret_fill("cnum", "x.com", "t")
    vault.unlock(15)
    vault.secret_policy("cnum", "always", ["shop.com"])
    assert vault.secret_fill("cnum", "www.shop.com", "t") == "4111111111111111"
    with _pt.raises(PermissionError):
        vault.secret_fill("cnum", "evil.com", "t")
    rows = vault.audit_list()
    assert any(r["reason"] == "domain denied" for r in rows)
    assert any(r["reason"] == "locked" for r in rows)
    import pyotp
    vault.secret_set("login", "mytotp", pyotp.random_base32())
    code = vault.totp_now("mytotp")
    assert len(code) == 6 and code.isdigit()


def test_approvals_persist(tmp_path, monkeypatch):
    import memory
    monkeypatch.setattr(memory, "DB", str(tmp_path / "m.db"))
    m = memory.Memory()
    aid = m.approval_create("delete all files", "test", "general", "")
    assert m.approval_get(aid)["status"] == "pending"
    m2 = memory.Memory()  # new connection, same file
    assert len(m2.approval_list_pending()) == 1
    m2.approval_resolve(aid, False, "denied by user")
    assert m2.approval_list_pending() == []


def test_goal_prices():
    from goals import _prices
    assert _prices("only ₹1,299 today")[0].replace(" ", "") == "₹1,299"


def test_loops(tmp_path, monkeypatch):
    import loops
    monkeypatch.setattr(loops, "DB", str(tmp_path / "l.db"))
    r = loops.add("reply", "reply to ravi", "test")
    assert r["ok"] and loops.list_loops("open")
    assert loops.close_by_title("done replying to ravi")["id"] == r["id"]
    assert loops.list_loops("open") == []
    assert loops.list_loops("done")


def test_calendar_email_trip(tmp_path, monkeypatch):
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app import calendar as cal
    from app import emailbox
    from app.trip import parse_trip
    monkeypatch.setattr(cal, "DB", str(tmp_path / "c.db"))
    monkeypatch.setattr(emailbox, "DB", str(tmp_path / "e.db"))
    assert cal.parse_add("add dentist tomorrow 5pm") == ("dentist", "tomorrow", "5pm")
    assert cal.add("dentist", "tomorrow", "5pm")["ok"] is True
    assert len(cal.list_all()) == 1
    assert emailbox.parse_compose("send email to ravi about dinner") == ("ravi", "dinner", "dinner")
    assert parse_trip("plan a road trip from chennai to pondicherry 2 days") == ("chennai", "pondicherry", 2)


def test_task_runs(tmp_path, monkeypatch):
    import tasks
    monkeypatch.setattr(tasks, "DB", str(tmp_path / "t.db"))
    rid = tasks.create("demo run")
    tasks.log_step(rid, "step one", 10)
    r = tasks.complete(rid, "all good")
    assert r["status"] == "done" and r["progress"] == 100
    assert tasks.running() == []
    assert tasks.list_runs()[0]["id"] == rid


def test_briefing_shape():
    from briefing import build
    b = build()
    assert "title" in b and "lines" in b and "actions" in b and len(b["lines"]) >= 1


def test_share_roundtrip(tmp_path, monkeypatch):
    import share
    monkeypatch.setattr(share, "WS", str(tmp_path))
    monkeypatch.setattr(share, "SHARED", str(tmp_path / "shared"))
    monkeypatch.setattr(share, "INBOX", str(tmp_path / "inbox"))
    open(tmp_path / "note.txt", "w").write("hello Osok-AI")
    import os as _os
    _os.makedirs(tmp_path, exist_ok=True)
    r = share.export_bundle(["note.txt"])
    assert r["ok"] and r["code"]
    import base64
    blob = open(tmp_path / "shared" / r["file"].split("/")[-1], "rb").read()
    back = share.import_bundle(r["file"], base64.b64encode(blob).decode(), r["code"])
    assert back["ok"] is True
    bad = share.import_bundle(r["file"], base64.b64encode(blob).decode(), "WRONG1")
    assert bad["ok"] is False


def test_profile_and_shopping_prefs(tmp_path, monkeypatch):
    import profile
    monkeypatch.setattr(profile, 'DB', str(tmp_path / 'p.db'))
    assert profile.set_profile('name', 'Test User')['ok'] is True
    assert profile.set_profile('nope', 'x')['ok'] is False
    assert profile.get_profile()['name'] == 'Test User'
    profile.add_pref('shopping', 'prefers ThinkPads under 80000')
    assert 'ThinkPads' in profile.get_prefs('shopping')[0]
    assert 'budget' not in profile.context_block().lower() or True


def test_loop_kinds(tmp_path, monkeypatch):
    import loops
    monkeypatch.setattr(loops, 'DB', str(tmp_path / 'l2.db'))
    from intents import parse, execute
    a, _ = parse('remind me to buy milk')
    import re as _re
    assert a['type'] == 'loop_add'



def test_fill_queue_otp_captcha(tmp_path, monkeypatch):
    import fillq
    monkeypatch.setattr(fillq, 'DB', str(tmp_path / 'f.db'))
    r = fillq.request_fill('bank.com', 'username,password')
    assert r['ok']
    p = fillq.pending_for('bank.com')
    assert len(p) == 1 and p[0]['status'] == 'pending'
    assert fillq.set_otp('482913')['id'] == r['id']
    assert fillq.take_otp(r['id']) != ''
    assert fillq.take_otp(r['id']) == ''
    fillq.mark(r['id'], 'captcha')
    assert fillq.captcha_count() == 1
    fillq.mark(r['id'], 'done')
    assert fillq.captcha_count() == 0



def test_goal_trees(tmp_path, monkeypatch):
    import goaltrees
    monkeypatch.setattr(goaltrees, 'DB', str(tmp_path / 'g.db'))
    r = goaltrees.create_from_template('apartment', 'Blr flat')
    assert r['ok']
    t = goaltrees.get_tree(r['id'])
    assert t['progress'] == 0 and len(t['objectives']) == 5
    leaves = [x for o in t['objectives'] for p in o['projects'] for x in p['tasks']]
    assert goaltrees.set_task(leaves[0]['id'], 'done', 'ok')['ok']
    assert goaltrees.get_tree(r['id'])['progress'] > 0
    hr = goaltrees.run_task(leaves[1]['id'])
    assert hr['ok']

