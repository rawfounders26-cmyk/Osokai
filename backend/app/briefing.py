"""Proactive briefing — Osok-AI's morning push. Aggregates everything that needs
attention: approvals, debts, goal alerts, wardrobe weather, recent runs."""
import datetime

try:
    from app import tasks as _runs
    from app.bills import list_groups
    from app.goals import alerts as goal_alerts
    from app.memory import Memory
    from app.wardrobe import weather as w_weather, suggest as w_suggest
    from app.connectors import list_connectors
except ImportError:
    import tasks as _runs
    from bills import list_groups
    from goals import alerts as goal_alerts
    from memory import Memory
    from wardrobe import weather as w_weather, suggest as w_suggest
    from connectors import list_connectors


def build():
    mem = Memory()
    lines, actions = [], []

    pend = mem.approval_list_pending()
    if pend:
        lines.append(f"{len(pend)} approval(s) waiting")
        actions.append({"label": "Review approvals", "go": "approvals"})

    owe = owed = 0
    try:
        for g in list_groups():
            for d in g.get("balances", []):
                if d.get("from") == "Me":
                    owe += d.get("amount", 0)
                if d.get("to") == "Me":
                    owed += d.get("amount", 0)
    except Exception:
        pass
    if owe or owed:
        lines.append(f"money: you owe ₹{owe}, owed ₹{owed}")
        actions.append({"label": "Open bill splitter", "go": "bills"})

    try:
        ga = goal_alerts(unseen_only=True)
    except Exception:
        ga = []
    if ga:
        lines.append(f"{len(ga)} goal alert(s): " + "; ".join(a["text"][:80] for a in ga[:3]))
        actions.append({"label": "Check goals", "go": "goals"})

    try:
        w = w_weather()
        if w.get("temp") is not None:
            lines.append(f"weather {w['temp']}°C" + (f", humid {w['humidity']}%" if w.get("humidity") else ""))
    except Exception:
        w = {}

    try:
        sug = w_suggest()
        cands = (sug.get("candidates") or [])[:2]
        if cands:
            pick = ", ".join(f"{c.get('color','')} {c.get('category','')}".strip() for c in cands)
            lines.append(f"wear: {pick}")
            actions.append({"label": "Outfit details", "go": "outfit"})
    except Exception:
        pass

    try:
        runs = _runs.running()
    except Exception:
        runs = []
    if runs:
        lines.append(f"{len(runs)} task(s) still running")

    try:
        n_conn = sum(1 for c in list_connectors() if c.get("connected"))
        if n_conn == 0:
            lines.append("no services connected yet")
            actions.append({"label": "Connect services", "go": "connectors"})
    except Exception:
        pass

    day = datetime.datetime.now().strftime("%A, %d %b")
    title = f"Good morning — {day}" if datetime.datetime.now().hour < 12 else f"Good evening — {day}"
    if not lines:
        lines.append("all clear. No approvals, debts, or alerts.")
    return {"title": title, "lines": lines, "actions": actions}
