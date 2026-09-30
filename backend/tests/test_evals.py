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
