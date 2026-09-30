"""Research + agent-builder. Deep multi-hop web research into report files;
scaffold new runnable agents under workspace/agents/ + registry."""
import os
import re
import time

try:
    from app.paths import ws as _pws
except ImportError:
    from paths import ws as _pws

WS = _pws()

try:
    from app.agent import _web_search
    from app.make import write_file
except ImportError:
    from agent import _web_search
    from make import write_file


def deep_research(topic: str, depth: int = 3) -> str:
    """Search broadly, fetch top sources, synthesize into a report file."""
    try:
        from app.agent import _run_tool as _rt
    except ImportError:
        from agent import _run_tool as _rt
    found = _web_search(topic)
    urls = re.findall(r"https?://[^\s)]+", found)[: max(2, depth)]
    notes = [f"QUERY: {topic}\n{found[:2000]}"]
    for u in urls[:4]:
        notes.append(f"SOURCE {u}\n{_rt('fetch_url', {'url': u})[:2500]}")
    fp = write_file(f"research-{re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')[:40]}.md",
                    f"# Research: {topic}\n\n" + "\n\n---\n\n".join(notes))
    return fp


def build_agent(name: str, purpose: str, tools: str = "") -> str:
    """Scaffold a runnable sub-agent package + register it. Meta power: agents building agents."""
    import json as _j
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "agent"
    base = os.path.join(WS, "agents", slug)
    os.makedirs(base, exist_ok=True)
    use_tools = [t.strip() for t in (tools or "web_search,write_file").split(",") if t.strip()]
    code = ('"""' + slug + ' — built by Osok-AI. Purpose: ' + purpose + '"""\n'
            'TOOLS = ' + repr(use_tools) + '\n\n'
            'def run(task: str) -> str:\n'
            '    """Entry point: sub-agent receives a task string."""\n'
            '    return f"' + slug + ' ready. Tools: {TOOLS}. Task received: {task}"\n')
    open(os.path.join(base, "agent.py"), "w").write(code)
    open(os.path.join(base, "SKILL.md"), "w").write(
        f"---\nname: {slug}\ndescription: {purpose}\n---\n\n# {name}\n\nBuilt by Osok-AI. Tools: {', '.join(use_tools)}.\n")
    regp = os.path.join(WS, "agents", "registry.json")
    try:
        reg = _j.load(open(regp))
    except Exception:
        reg = []
    reg = [r for r in reg if r.get("slug") != slug] + [
        {"slug": slug, "name": name, "purpose": purpose, "tools": use_tools, "ts": time.time()}]
    open(regp, "w").write(_j.dumps(reg, indent=1))
    return base


def list_agents():
    import json as _j
    regp = os.path.join(WS, "agents", "registry.json")
    try:
        return _j.load(open(regp))
    except Exception:
        return []
