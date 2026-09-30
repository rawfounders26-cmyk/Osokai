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

# ---- cloud pack evals: portable paths, relay key preference ----

def test_paths_env_override(tmp_path, monkeypatch):
    import paths
    monkeypatch.setenv("OSOKAI_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OSOKAI_WS_DIR", str(tmp_path / "ws"))
    assert paths.data("osokai.db") == str(tmp_path / "data" / "osokai.db")
    assert paths.ws() == str(tmp_path / "ws")
    monkeypatch.delenv("OSOKAI_DATA_DIR")
    assert paths.data("x").endswith("x")


def test_relay_key_preference(tmp_path, monkeypatch):
    import relay
    monkeypatch.setattr(relay, "DB", str(tmp_path / "rl2.db"))
    monkeypatch.setenv("OSOKAI_AUTH_TOKEN", "token-A")
    monkeypatch.setenv("OSOKAI_RELAY_KEY", "relay-B")
    k1 = relay._key()
    monkeypatch.delenv("OSOKAI_RELAY_KEY")
    k2 = relay._key()
    assert k1 != k2  # dedicated relay key wins when present
    r = relay.seal("phone", {"a": 1})
    assert r["ok"] and relay.unseal(relay.pull("phone")[0]["envelope"]) == {"a": 1}

# ---- v0.5 evals: e2e keys, slm slot, wake vad, optimizer, share links, digests ----

def test_e2e_server_blind_roundtrip(tmp_path, monkeypatch):
    import e2e
    monkeypatch.setattr(e2e, "DB", str(tmp_path / "e.db"))
    phone = e2e.generate_keypair()
    desk = e2e.generate_keypair()
    assert e2e.register("phone", phone["public"])["ok"]
    assert e2e.register("desk", desk["public"])["ok"]
    assert e2e.register("evil", "not-a-key")["ok"] is False
    env = e2e.seal_to(phone["private"], desk["public"], "phone", {"text": "meet at 8"})
    assert e2e.push_envelope("desk", env)["ok"]
    assert e2e.push_envelope("desk", {"v": 1})["ok"] is False
    pulled = e2e.pull_envelopes("desk")
    assert len(pulled) == 1
    blob = pulled[0]["envelope"]["ct"]
    assert "meet at 8" not in blob  # server-blind ciphertext
    opened = e2e.open_envelope(desk["private"], pulled[0]["envelope"])
    assert opened == {"from": "phone", "payload": {"text": "meet at 8"}}
    assert e2e.pull_envelopes("desk") == []


def test_slm_slot_escalates(monkeypatch):
    import slm
    monkeypatch.setattr(slm, "_has", lambda m: False)  # no local backends: must escalate
    st = slm.status()
    assert st["available"] is False and "llama-cpp-python" in st["hint"]
    try:
        slm.generate("hello")
        assert False, "should escalate"
    except RuntimeError as e:
        assert str(e) == "no-slm"


def test_wake_vad_and_config(tmp_path, monkeypatch):
    import struct
    import wake
    monkeypatch.setattr(wake, "DB", str(tmp_path / "w.db"))
    silence = struct.pack("<800h", *([0] * 800))
    loud = struct.pack("<800h", *([2000] * 800))
    assert wake.vad(silence)["speech"] is False
    assert wake.vad(loud)["speech"] is True
    assert wake.get_config()["keyword"] == "hey osok"
    wake.set_config(keyword="ok osok")
    assert wake.get_config()["keyword"] == "ok osok"
    sid = wake.stream_start()
    r = wake.stream_chunk(sid, __import__("base64").b64encode(loud).decode(), ms=100)
    assert r["ok"] and r["speech"] is True and r["ended"] is False


def test_optimizer_routes_and_report(tmp_path, monkeypatch):
    import usage
    import optimizer
    monkeypatch.setattr(usage, "DB", str(tmp_path / "u2.db"))
    usage.log("chat", "m", "x" * 400, "y" * 400, 100)
    assert optimizer.recommend("chat", 1.0)["route"] == "local"
    assert optimizer.recommend("chat", 0.3)["route"] == "groq"
    assert optimizer.recommend("chat", 0.7)["route"] == "groq"  # no weights: escalate, flagged
    assert optimizer.recommend("chat", 0.7, slm_ready=True)["route"] == "slm"
    rep = optimizer.report(30)
    assert rep["by_task"]["chat"]["calls"] >= 1 and "policy" in rep


def test_share_links_lifecycle(tmp_path, monkeypatch):
    import sqlite3
    import share
    db = sqlite3.connect(str(tmp_path / "s.db"))
    db.execute("CREATE TABLE share_links(token TEXT PRIMARY KEY, kind TEXT, ref INT, exp REAL, revoked INT DEFAULT 0, ts REAL)")
    monkeypatch.setattr(share, "_ldb", lambda: db)
    assert share.create_link("nonsense", 1)["ok"] is False
    r = share.create_link("goal", 7, ttl_hours=1)
    assert r["ok"] and r["url"].startswith("/s/")
    assert share.resolve_link(r["token"]) == {"kind": "goal", "ref": 7}
    assert share.resolve_link("bogus") is None
    assert "not found" in share.render_goal_page(999999).lower()
    share.revoke_link(r["token"])
    assert share.resolve_link(r["token"]) is None
    assert len(share.list_links()) == 1


def test_digest_topics_and_schedule_kind(tmp_path, monkeypatch):
    import digest
    import schedules
    monkeypatch.setattr(digest, "DB", str(tmp_path / "d.db"))
    monkeypatch.setattr(schedules, "DB", str(tmp_path / "s2.db"))
    t = digest.add_topic("UPI trends")
    assert t["ok"] and len(digest.list_topics()) == 1
    assert digest.add_topic("")["ok"] is False
    j = schedules.create("nightly", "research_digest", {"topic": "UPI trends"}, every_min=1440)
    assert j["ok"]
    monkeypatch.setattr(digest, "run_digest", lambda topic: {"ok": True, "note": f"mock {topic}"})
    try:
        import app.digest as _ad
        monkeypatch.setattr(_ad, "run_digest", lambda topic: {"ok": True, "note": f"mock {topic}"})
    except ImportError:
        pass
    r = schedules.execute({"kind": "research_digest", "args": {"topic": "UPI trends"}})
    assert r["ok"] and "mock" in r["note"]

# ---- v0.6 evals: sandbox runtime, handoff, slm fetch ----

def test_runtime_jail_and_gates(tmp_path, monkeypatch):
    import runtime
    import sandbox
    monkeypatch.setattr(runtime, "DB", str(tmp_path / "rt.db"))
    monkeypatch.setattr(sandbox, "DB", str(tmp_path / "rt2.db"))
    monkeypatch.setattr(runtime, "WS", str(tmp_path))
    r = runtime.run("demo", "nope", {})
    assert r["ok"] is False and "allow-listed" in r["error"]
    r = runtime.run("demo", "read_file", {"path": "../../evil.txt"})
    assert r["ok"] is False  # denied: no grant yet
    sandbox.grant("demo", ["files.read", "loops.write"])
    try:
        import app.sandbox as _asb
        monkeypatch.setattr(_asb, "DB", str(tmp_path / "rt2.db"))
        _asb.grant("demo", ["files.read", "loops.write"])
    except ImportError:
        pass
    r = runtime.run("demo", "read_file", {"path": "../../evil.txt"})
    assert r["ok"] is False and "jail" in r["error"]  # grant held, jail still bites
    r = runtime.run("demo", "web_fetch", {"url": "https://example.com"})
    assert r["ok"] is False  # net off: no grant
    r = runtime.run("demo", "append_note", {"text": "runtime probe"})
    assert r["ok"] is True
    runtime.kill("demo")
    assert runtime.run("demo", "append_note", {"text": "x"})["ok"] is False
    runtime.unkill("demo")
    assert runtime.run("demo", "append_note", {"text": "x"})["ok"] is True
    aud = runtime.audit("demo")
    assert len(aud) >= 4 and any(not a["allowed"] for a in aud)


def test_handoff_single_accept(tmp_path, monkeypatch):
    import handoff
    import goaltrees
    monkeypatch.setattr(handoff, "DB", str(tmp_path / "h.db"))
    monkeypatch.setattr(goaltrees, "DB", str(tmp_path / "hg.db"))
    try:
        import app.goaltrees as _ag
        monkeypatch.setattr(_ag, "DB", str(tmp_path / "hg.db"))
    except ImportError:
        pass
    gid = goaltrees.create_from_template("trip", "Probe trip")["id"]
    h = handoff.create(gid, "desktop", "phone")
    assert h["ok"] and h["progress"] == 0
    assert handoff.create(999999, "desktop", "phone")["ok"] is False
    assert len(handoff.pending("phone")) == 1
    a = handoff.accept(h["id"], "laptop")
    assert a["ok"] is False  # wrong device
    a = handoff.accept(h["id"], "phone")
    assert a["ok"] and "resume" in a
    assert handoff.accept(h["id"], "phone")["ok"] is False  # single-accept
    assert handoff.pending("phone") == []


def test_slm_fetch_rejects_garbage():
    import slm
    assert slm.fetch_weights("not-a-url")["ok"] is False
    assert slm.fetch_weights("https://example.com/nonexistent-xyz.gguf")["ok"] is False
