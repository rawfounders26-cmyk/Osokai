"""Osok-AI evals — nightly success probes. Intent battery, router battery,
bills edge cases, vault policy matrix, URL sanitizer battery."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from intents import parse
from skills_index import route

INTENT_CASES = [
    ("play despacito", "youtube_play"),
    ("watch the office episode 2", "youtube_play"),
    ("open youtube and watch IPL highlights", "youtube_play"),
    ("open dog images", "open_url"),
    ("open google and search cute cats", "open_url"),
    ("open google and search dogs and save 2 images on desktop", "search_save_images"),
    ("search mens shoes under 2000", "shop_browse"),
    ("open blinkit", "open_url"),
    ("youtube thira", "open_url"),
    ("radhima paatu podu", "youtube_play"),
    ("dog photos thedu", "open_url"),
    ("open chrome", "open_app"),
    ("open notepad", "open_app"),
    ("remind me to call mom tomorrow 9am", "loop_add"),
    ("done calling mom", "loop_done"),
    ("track gym subscription", "track"),
    ("resize photo.jpg to 800", "img"),
    ("convert a.png to jpg", "img"),
    ("compress pic.jpg to 50", "img"),
    ("thumbnail of banner.jpg 128", "img"),
    ('meme pic.jpg "TOP" "BOTTOM"', "img"),
]


def test_intent_battery():
    for text, want in INTENT_CASES:
        got, _ = parse(text)
        assert got and got["type"] == want, f"{text!r} -> {got}"


def test_router_battery():
    assert route("prepare a ppt on EVs")[0] == "pptx"
    assert "legal-risk-assessment-zacharie-laik" in route("draft a legal notice")
    assert "seo-audit" in route("do SEO audit")
    assert "fashion-stylist" in route("what should i wear today")
    assert "logo-design" in route("design a logo for my cafe")


def test_bills_custom_splits(tmp_path, monkeypatch):
    import bills
    monkeypatch.setattr(bills, "DB", str(tmp_path / "b.db"))
    g = bills.create_group("flat", ["A", "B", "C"])
    bills.add_expense(g["id"], "Rent", 9000, "A", {"A": 3000, "B": 3000, "C": 3000})
    b = bills.balances(g["id"])
    assert b["debts"] == [{"from": "B", "to": "A", "amount": 3000.0},
                          {"from": "C", "to": "A", "amount": 3000.0}]
    bills.settle(g["id"], "B", "A", 3000)
    assert bills.balances(g["id"])["debts"] == [{"from": "C", "to": "A", "amount": 3000.0}]


def test_url_sanitizer_battery():
    from system_tools import clean_url, sanitize_reply
    assert clean_url('"https//www.youtube.com"') == "https://www.youtube.com"
    assert clean_url("https://mail.google.com") == "https://mail.google.com"
    assert clean_url("www.example.com") == "https://www.example.com"
    out = sanitize_reply('watch it here https//example.com/a%22 now')
    assert "https//" not in out and "%22" not in out

# ---- v0.2 scale-up evals: proactive, orchestrator, memory 2.0, RAG, presence ----

def test_proactive_nudge_dedup(tmp_path, monkeypatch):
    import proactive
    monkeypatch.setattr(proactive, "DB", str(tmp_path / "p.db"))
    assert proactive.nudge("loop_due", "loop:1", "Reminder due: call mom") is True
    assert proactive.nudge("loop_due", "loop:1", "Reminder due: call mom") is False  # dedup window
    assert len(proactive.list_nudges()) == 1
    proactive.mark_seen()
    assert proactive.list_nudges() == []


def test_orchestrator_critic_failopen(monkeypatch):
    import orchestrator
    import grok_client
    def _boom(*a, **k):
        raise RuntimeError("429")
    monkeypatch.setattr(grok_client, "chat_with_grok", _boom)
    try:
        import app.grok_client as _ag
        monkeypatch.setattr(_ag, "chat_with_grok", _boom)
    except ImportError:
        pass
    c = orchestrator._critic("do thing", "did thing")
    assert c["verdict"] == "accept"  # fail-open, never blocks autonomy


def test_orchestrator_missing_goal(tmp_path, monkeypatch):
    import orchestrator
    import goaltrees
    monkeypatch.setattr(goaltrees, "DB", str(tmp_path / "g.db"))
    r = orchestrator.auto_step(99999)
    assert r["ok"] is False and "not found" in r["error"]


def test_memory_facts_recall(tmp_path, monkeypatch):
    import memory
    monkeypatch.setattr(memory, "DB", str(tmp_path / "m2.db"))
    m = memory.Memory()
    m.note_fact("user is vegetarian", salience=3.0)
    m.note_fact("likes cricket", salience=1.0)
    hits = m.recall("vegetarian food")
    assert hits and hits[0]["fact"] == "user is vegetarian"


def test_rag_overlap_and_hybrid(tmp_path, monkeypatch):
    import rag
    monkeypatch.setattr(rag, "DB", str(tmp_path / "r.db"))
    monkeypatch.setattr(rag, "WS", str(tmp_path))
    (tmp_path / "notes.md").write_text("Osok-AI briefing protocol. " + ("filler sentence here. " * 200) + "secret keyword zebra.")
    out = rag.ingest()
    assert out["ok"] and out["total_chunks"] >= 2  # overlap splits long docs
    hits = rag.search("zebra")
    assert hits and hits[0]["path"] == "notes.md" and "#" in hits[0]["cite"]
    ans = rag.answer("what is the zebra keyword")
    assert ans["ok"] and ans["citations"]


def test_presence_offline_queue(tmp_path, monkeypatch):
    import presence
    monkeypatch.setattr(presence, "DB", str(tmp_path / "d.db"))
    presence.heartbeat("phone")
    presence.queue("phone", "nudge", {"text": "hi"})
    first = presence.pending("phone")
    assert len(first) == 1 and first[0]["payload"]["text"] == "hi"
    assert presence.pending("phone") == []  # delivered once

# ---- v0.3 scale-up evals: fast lane, usage, marketplace, teams, voice ----

def test_local_fast_lane():
    from local import try_answer
    assert "2026" in try_answer("what is todays date") or "September" in try_answer("date")
    assert try_answer("what is 12 * 8 + 4") == "12 * 8 + 4 = 100"
    assert try_answer("convert 10 km to mi") == "10 km = 6.214 mi"
    assert try_answer("ping") == "Online and local-first. All systems nominal."
    assert try_answer("what time is it").startswith("It's ")
    assert try_answer("what is the time").startswith("It's ")
    assert try_answer("help me plan a startup raising funds") is None  # escalates
    assert try_answer("open youtube and play something") is None


def test_usage_logging_and_budget(tmp_path, monkeypatch):
    import usage
    monkeypatch.setattr(usage, "DB", str(tmp_path / "u.db"))
    usage.log("chat", "test-model", "hello", "hi there", 12)
    usage.log("research", "test-model", "x" * 100000, "y" * 20000, 500)
    s = usage.summary(30)
    assert s["months"] and s["months"][0]["calls"] >= 1 and s["by_task"]
    assert usage.get_budget() == 0.0 and usage.budget_ok() is True
    usage.set_budget(0.0001)
    assert usage.budget_ok() is False  # cap enforced for autonomy


def test_marketplace_verify_install(tmp_path, monkeypatch):
    import hashlib
    import json
    import marketplace
    monkeypatch.setenv("OSOKAI_AUTH_TOKEN", "test-key")
    monkeypatch.setattr(marketplace, "MARKET", str(tmp_path / "mkt"))
    monkeypatch.setattr(marketplace, "ROLES", str(tmp_path / "roles"))
    monkeypatch.setattr(marketplace, "DB", str(tmp_path / "m.db"))
    d = tmp_path / "mkt" / "demo"
    d.mkdir(parents=True)
    body = b"# Demo\nDo things.\n"
    (d / "SKILL.md").write_bytes(body)
    (d / "manifest.json").write_text(json.dumps({
        "name": "demo", "version": "1.0", "description": "d", "perms": [],
        "sha256": hashlib.sha256(body).hexdigest(), "sig": marketplace.sign_pack(body)}))
    assert marketplace.verify("demo")["ok"]
    assert marketplace.install("demo")["ok"]
    (d / "SKILL.md").write_bytes(body + b"evil")
    assert marketplace.verify("demo")["ok"] is False  # tamper detected


def test_teams_flow(tmp_path, monkeypatch):
    import teams
    monkeypatch.setattr(teams, "DB", str(tmp_path / "t.db"))
    t = teams.create_team("founders", owner="ceo")
    assert teams.add_member(t["id"], "cto")["ok"]
    assert len(teams.list_teams()[0]["members"]) == 2
    a = teams.ask_team(t["id"], "spend $50 on domain?", kind="payment")
    assert teams.team_pending(t["id"])[0]["id"] == a["id"]
    r = teams.team_resolve(a["id"], "cto", True)
    assert r["approval"]["status"] == "allowed" and r["approval"]["by"] == "cto"
    assert teams.team_pending(t["id"]) == []

# ---- v0.4 scale-up evals: schedules, sandbox, team roles/billing, relay, SLM routing ----

def test_schedules_crud_and_run(tmp_path, monkeypatch):
    import schedules
    monkeypatch.setattr(schedules, "DB", str(tmp_path / "s.db"))
    j = schedules.create("scan", "nudge_scan", {}, every_min=60)
    assert j["ok"] and len(schedules.list_jobs()) == 1
    assert schedules.create("bad", "nope")["ok"] is False
    assert schedules.create("noname", "briefing")["ok"] is False  # no schedule
    r = schedules.execute({"kind": "nudge_scan", "args": {}})
    assert r["ok"]
    schedules.set_enabled(j["id"], False)
    assert schedules.list_jobs()[0]["enabled"] is False
    schedules.remove(j["id"])
    assert schedules.list_jobs() == []


def test_sandbox_gates_and_reputation(tmp_path, monkeypatch):
    import sandbox
    monkeypatch.setattr(sandbox, "DB", str(tmp_path / "sb.db"))
    assert sandbox.check("demo", "files.write") is False  # default deny
    sandbox.grant("demo", ["files.read"])
    assert sandbox.check("demo", "files.read") is True
    assert sandbox.check("demo", "vault.read") is False
    try:
        sandbox.guard("demo", "vault.read")
        assert False, "should raise"
    except PermissionError:
        pass
    assert sandbox.reputation("demo")["stars"] == 0.0
    sandbox.rate("demo", "u1", 5)
    assert sandbox.reputation("demo")["stars"] == 5.0


def test_team_roles_and_billing(tmp_path, monkeypatch):
    import teams
    monkeypatch.setattr(teams, "DB", str(tmp_path / "t2.db"))
    t = teams.create_team("acme", owner="ceo")
    tid = t["id"]
    teams.add_member(tid, "cto")
    assert teams.role_of(tid, "ceo") == "owner"
    assert teams.can(tid, "ceo", "manage") and not teams.can(tid, "cto", "manage")
    assert teams.set_role(tid, "cto", "ceo", "member")["ok"] is False  # not admin
    assert teams.set_role(tid, "ceo", "cto", "admin")["ok"]
    assert teams.set_role(tid, "cto", "intern", "viewer")["ok"]  # admin can add seats
    assert teams.role_of(tid, "intern") == "viewer"
    assert not teams.can(tid, "intern", "resolve")
    a = teams.ask_team(tid, "buy domain?")
    assert teams.team_resolve(a["id"], "intern", True)["ok"] is False  # viewer denied
    assert teams.team_resolve(a["id"], "cto", True)["approval"]["by"] == "cto"
    assert teams.set_budget(tid, "cto", 10.0)["ok"]
    sp = teams.spend(tid)
    assert sp["cap_usd"] == 10.0 and sp["total_usd"] == 0.0 and not sp["over_budget"]


def test_relay_sealed_roundtrip(tmp_path, monkeypatch):
    import relay
    monkeypatch.setattr(relay, "DB", str(tmp_path / "rl.db"))
    monkeypatch.setenv("OSOKAI_AUTH_TOKEN", "relay-test-key")
    r = relay.seal("phone", {"text": "secret hello"})
    assert r["ok"]
    envs = relay.pull("phone")
    assert len(envs) == 1
    assert "secret hello" not in envs[0]["envelope"]  # ciphertext at rest
    assert relay.unseal(envs[0]["envelope"]) == {"text": "secret hello"}
    assert relay.pull("phone") == []  # delivered once


def test_slm_confidence_routing():
    from local import confidence, try_answer
    assert confidence("what time is it") == 1.0
    assert confidence("") == 0.0
    assert 0.5 <= confidence("should i buy a house in bangalore") <= 0.9  # SLM zone, escalates today
    assert try_answer("should i buy a house in bangalore") is None

# ---- feature scale-up evals: outfit planner + bill splitting chat intents ----

def test_outfit_bill_intent_parse():
    from intents import parse
    cases = [
        ("plan my outfits for the week", "outfit_plan"),
        ("what should i wear to a wedding tomorrow", "outfit_occasion"),
        ("outfit for gym", "outfit_occasion"),
        ("pack for 3 days in goa", "outfit_pack"),
        ("i wore the blue shirt", "outfit_wore"),
        ("laundry done", "outfit_laundry"),
        ("add blue linen shirt to wardrobe", "outfit_add"),
        ("split 1200 for dinner with flat", "bill_quick"),
        ("split dinner 1200 with flat", "bill_quick"),
        ("settle up flat", "bill_settle_up"),
        ("settle", "bill_settle_up"),
        ("repeat rent 9000 monthly in flat paid by me", "bill_repeat"),
        ("house ledger for flat", "bill_house"),
    ]
    for text, want in cases:
        got, _ = parse(text)
        assert got and got["type"] == want, f"{text!r} -> {got}"


def test_wardrobe_scores_laundry_pack(tmp_path, monkeypatch):
    import wardrobe
    monkeypatch.setattr(wardrobe, "DB", str(tmp_path / "w.db"))
    a = wardrobe.add_item("linen shirt", "blue", "all", "smart-casual")["id"]
    b = wardrobe.add_item("gym shorts", "black", "all", "activewear")["id"]
    wardrobe.feedback(a, True)
    wardrobe.feedback(b, False)
    items = {i["id"]: i for i in wardrobe.list_items()}
    assert items[a]["likes"] == 1 and items[b]["dislikes"] == 1
    assert wardrobe.score(items[a]) > wardrobe.score(items[b])
    assert wardrobe.occasion_formality("cousin wedding") == "formal"
    assert wardrobe.occasion_formality("morning gym") == "activewear"
    wardrobe.mark_worn(a)
    assert wardrobe.laundry_days() == 7
    s = wardrobe.suggest()
    assert s["candidates"][0]["id"] == b  # worn item guarded out by laundry cycle
    wardrobe.laundry_done()
    assert len(wardrobe.suggest()["candidates"]) == 2
    p = wardrobe.pack_trip(3, "Goa")
    assert p["ok"] and "Goa" in p["reply"]


def test_bills_recurring_upi_ledger(tmp_path, monkeypatch):
    import bills
    monkeypatch.setattr(bills, "DB", str(tmp_path / "b2.db"))
    g = bills.create_group("flat", ["Me", "A"])["id"]
    assert bills.find_group("flat")["id"] == g
    bills.set_upi(g, "A", "a@upi")
    assert bills.members(g)[1]["upi"] == "a@upi"
    bills.add_expense(g, "Dinner", 1000, "Me", {})
    s = bills.settle_up(g)
    assert s["debts"] and s["debts"][0]["upi"] == ""  # creditor Me has no UPI yet
    bills.set_upi(g, "Me", "me@upi")
    s = bills.settle_up(g)
    assert s["debts"][0]["upi"].startswith("upi://pay?pa=me%40upi")
    assert "a%40upi" in bills.upi_link("a@upi", "A", 500)
    r = bills.add_recurring(g, "Rent", 9000, "Me", {}, 1)
    assert r["ok"] and len(bills.list_recurring(g)) == 1
    h = bills.house_ledger(g)
    assert h["ok"] and h["total"] == 1000 and "flat" in h["reply"]
