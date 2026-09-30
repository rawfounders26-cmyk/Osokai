"""Trip planner — India-first road trips. Researches route/stays/food, writes itinerary file."""
import re

try:
    from app.make import write_file
    from app.agent import _web_search, _browser
except ImportError:
    from make import write_file
    from agent import _web_search, _browser


def plan_trip(origin: str, dest: str, days: int = 3) -> str:
    q1 = _web_search(f"{origin} to {dest} road trip route best stops")
    q2 = _web_search(f"best hotels stay {dest} budget family")
    q3 = _web_search(f"{dest} must eat local food places")
    md = (f"# Road trip: {origin} → {dest} ({days} days)\n\n"
          f"_Planned by Osok-AI. Verify bookings before paying._\n\n"
          f"## Route research\n{q1[:1500]}\n\n## Stay options\n{q2[:1500]}\n\n"
          f"## Food\n{q3[:1200]}\n\n## Checklist\n"
          f"- [ ] Confirm hotel booking (free cancellation)\n- [ ] Fuel + FASTag balance\n"
          f"- [ ] PUC, insurance, license copies\n- [ ] Offline maps downloaded\n")
    name = f"trip-{re.sub(r'[^a-z]+', '-', (origin + '-' + dest).lower()).strip('-')}.md"
    fp = write_file(name, md)
    return f"Trip plan saved: {fp}. {days}-day outline with route, stays, food + checklist."


def parse_trip(text: str):
    m = re.match(r"^(?:plan|organize|organise)\s+(?:a\s+|my\s+)?(?:road\s+)?trip\s+(?:from\s+)?(.+?)\s+to\s+(.+?)(?:\s+(\d+)\s*days?)?$", text.strip(), re.I)
    if m:
        return m.group(1).strip(), m.group(2).strip(), int(m.group(3) or 3)
    return None
