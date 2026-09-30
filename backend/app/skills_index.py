"""Skills registry + role router — picks the right pro(s) for any task/goal.
Scans backend/skills/roles/*/SKILL.md frontmatter (name + description)."""
import os, re

ROLES = os.path.join(os.path.dirname(__file__), "..", "skills", "roles")

_ROLE_ALIASES = {
    "software engineer": ["senior-fullstack", "senior-frontend", "senior-devops", "crewai", "langgraph"],
    "coding": ["senior-fullstack", "senior-frontend"],
    "designer": ["frontend-ui-engineering", "landing"],
    "designing": ["frontend-ui-engineering", "landing"],
    "editor": ["copywriting", "content-strategy"],
    "editing": ["copywriting"],
    "executive assistant": ["reach-inbox-zero", "transcribe-meetings-follow-up", "prepare-for-calls", "prepare-for-sales-meetings"],
    "hire": ["getting-started-with-recruiting-in-strawberry", "onboard-offboard-teammates", "screen-applicants-against-job-description"],
    "hiring": ["getting-started-with-recruiting-in-strawberry", "screen-applicants-against-job-description"],
    "developer": ["senior-fullstack", "getting-started-with-recruiting-in-strawberry"],
    "human resource": ["getting-started-with-recruiting-in-strawberry", "onboard-offboard-teammates", "screen-applicants-against-job-description"],
    "tester": ["playwright-skill", "performance-optimization"],
    "testing": ["playwright-skill", "performance-optimization"],
    "research": ["deep-research", "market-research", "extract-web-data", "perplexity"],
    "excel": ["startup-financial-modeling"],
    "spreadsheet": ["startup-financial-modeling"],
    "ppt": ["pptx"],
    "presentation": ["pptx"],
    "powerpoint": ["pptx"],
    "powerbi": ["startup-financial-modeling", "market-research"],
    "dashboard": ["startup-financial-modeling", "market-research"],
    "business analyst": ["market-research", "build-structured-investment-memo-any-company"],
    "product manager": ["product-manager", "techwavedev-product-manager"],
    "project manager": ["build-client-progress-report-project-tools", "product-manager"],
    "hacker": ["cybersecurity"],
    "code review": ["ecc-code-reviewer", "ecc-security-reviewer"],
    "review my code": ["ecc-code-reviewer"],
    "plan": ["ecc-planner", "ecc-architect"],
    "architect": ["ecc-architect"],
    "refactor": ["ecc-refactor-cleaner"],
    "tdd": ["ecc-tdd-guide", "tdd-workflow"],
    "e2e": ["ecc-e2e-runner", "playwright-skill"],
    "build error": ["ecc-build-error-resolver"],
    "document": ["ecc-doc-updater"],
    "backend": ["ecc-backend-patterns", "senior-fullstack"],
    "frontend": ["ecc-frontend-patterns", "senior-frontend"],
    "verify": ["ecc-verification-loop", "eval-harness"],
    "learn": ["ecc-continuous-learning"],
    "trade": ["trading-team"],
    "stock": ["trading-team", "market-research"],
    "logo": ["logo-design"],
    "image": ["logo-design"],
    "thumbnail": ["logo-design"],
    "meme": ["logo-design"],
    "brand": ["logo-design"],
    "implement": ["mp-implement", "mp-prototype"],
    "debug": ["mp-diagnosing-bugs", "ecc-build-error-resolver"],
    "spec": ["mp-to-spec", "mp-to-tickets"],
    "ship": ["gstack-ship", "gstack-test"],
    "design review": ["gstack-design-review"],
    "scrape": ["gstack-scrape", "extract-web-data"],
    "figma": ["figma-to-react", "figma-patterns", "figma-templates"],
    "tailwind": ["figma-patterns", "figma-templates"],
    "handoff": ["figma-handoff"],
    "outfit": ["fashion-stylist"],
    "wear": ["fashion-stylist"],
    "wardrobe": ["fashion-stylist"],
    "dress": ["fashion-stylist"],
    "clothes": ["fashion-stylist"],
    " qa ": ["figma-qa"],
    "security": ["cybersecurity", "seo-audit"],
    "finance": ["startup-financial-modeling", "build-structured-investment-memo-any-company"],
    "ca ": ["startup-financial-modeling", "organize-receipts-bookkeeping"],
    "account": ["organize-receipts-bookkeeping", "research-an-account"],
    "lawyer": ["legal-risk-assessment-zacharie-laik"],
    "legal": ["legal-risk-assessment-zacharie-laik"],
    "seo": ["seo-audit", "programmatic-seo"],
    "marketing": ["content-strategy", "pricing-strategy", "audit-seo-create-report"],
    "sales": ["sales-engineer", "research-an-account", "prepare-for-calls"],
    "pdf": ["pdf"],
    "rag": ["rag-engineer"],
    "ai agent": ["crewai", "langgraph", "prompt-engineering"],
}

_cache = None

def _load():
    global _cache
    if _cache is not None:
        return _cache
    reg = {}
    base = os.path.normpath(ROLES)
    if os.path.isdir(base):
        for d in sorted(os.listdir(base)):
            fp = os.path.join(base, d, "SKILL.md")
            if not os.path.isfile(fp):
                continue
            try:
                head = open(fp, encoding="utf-8", errors="ignore").read(1500)
                m = re.search(r"description:\s*(.+)", head)
                reg[d] = (m.group(1).strip() if m else d)
            except Exception:
                reg[d] = d
    _cache = reg
    return reg

def list_roles():
    return [{"id": k, "description": v} for k, v in _load().items()]

def route(task: str, top: int = 2):
    """Return [skill_id,...] best matching the task. Always non-empty when registry exists."""
    t = " " + task.lower() + " "
    reg = _load()
    if not reg:
        return []
    scores = {}
    for alias, ids in _ROLE_ALIASES.items():
        if alias.strip() and alias in t:
            for i in ids:
                if i in reg:
                    scores[i] = scores.get(i, 0) + len(alias)
    if not scores:
        words = re.findall(r"[a-z]{4,}", t)
        for sid, desc in reg.items():
            blob = (sid + " " + desc).lower().replace("-", " ")
            s = sum(1 for w in words if w in blob)
            if s:
                scores[sid] = s
    ranked = sorted(scores, key=lambda k: -scores[k])
    return ranked[:top] or sorted(reg)[:top]

def _actionable_body(text: str, max_chars: int) -> str:
    """Strip YAML frontmatter; start from first heading. Frontmatter wastes the budget."""
    body = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)
    m = re.search(r"^# .+", body, flags=re.M)
    if m:
        body = body[m.start():]
    # prefer imperative content: keep steps/commands/checklists, drop long prose tails
    return body[:max_chars]

def role_context(skill_ids, max_chars: int = 600):
    """Actionable SKILL.md bodies to inject into the agent prompt."""
    base = os.path.normpath(ROLES)
    parts = []
    for sid in skill_ids:
        fp = os.path.join(base, sid, "SKILL.md")
        try:
            body = open(fp, encoding="utf-8", errors="ignore").read(max_chars + 800)
            parts.append(f"### Skill: {sid}\n{_actionable_body(body, max_chars)}")
        except Exception:
            pass
    return "\n\n".join(parts)[:max_chars * len(skill_ids)]
