"""GitHub connector — our own design. Repos, issues, and CI status for the
agent loop and the code-review watcher. Token from connector store or env
(GITHUB_TOKEN). Read-only by default; writes go through approval-gated paths."""
import os

API = "https://api.github.com"


def _token() -> str:
    try:
        try:
            from app.connectors import _load
            from app.vault import decrypt
        except ImportError:
            from connectors import _load
            from vault import decrypt
        entry = (_load() or {}).get("github", {})
        if entry.get("enc"):
            try:
                tok = decrypt(entry["enc"])
                if tok:
                    return tok
            except Exception:
                pass
    except Exception:
        pass
    return os.getenv("GITHUB_TOKEN", "")


def _get(path: str, params: dict = None):
    import httpx as _hx
    tok = _token()
    if not tok:
        return {"ok": False, "error": "no GitHub token: paste via /connectors/github/connect or set GITHUB_TOKEN"}
    try:
        r = _hx.get(f"{API}{path}",
                    headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"},
                    params=params or {}, timeout=30)
        if r.status_code == 401:
            return {"ok": False, "error": "GitHub token rejected (401)"}
        if r.status_code == 403 and "rate limit" in r.text.lower():
            return {"ok": False, "error": "GitHub rate limited — try later"}
        if r.status_code not in (200, 201):
            return {"ok": False, "error": f"github {r.status_code}: {r.text[:150]}"}
        return {"ok": True, "data": r.json()}
    except Exception as e:
        return {"ok": False, "error": f"github call failed: {e}"[:200]}


def repos(limit: int = 10):
    r = _get("/user/repos", {"sort": "updated", "per_page": max(1, min(30, limit))})
    if not r.get("ok"):
        return r
    return {"ok": True, "repos": [
        {"full": x.get("full_name", ""), "private": x.get("private", False),
         "stars": x.get("stargazers_count", 0), "open_issues": x.get("open_issues_count", 0),
         "pushed": (x.get("pushed_at", "") or "")[:10]} for x in r["data"]]}


def issues(owner_repo: str, state: str = "open", limit: int = 10):
    if "/" not in (owner_repo or ""):
        return {"ok": False, "error": "need owner/repo"}
    r = _get(f"/repos/{owner_repo}/issues",
             {"state": state if state in ("open", "closed", "all") else "open",
              "per_page": max(1, min(30, limit))})
    if not r.get("ok"):
        return r
    return {"ok": True, "issues": [
        {"number": x.get("number", 0), "title": x.get("title", ""),
         "labels": [l.get("name", "") for l in x.get("labels", [])],
         "is_pr": "pull_request" in x} for x in r["data"] if "pull_request" not in x]}


def ci_status(owner_repo: str, branch: str = ""):
    """Combined CI status: latest workflow runs (needs Actions permission)."""
    if "/" not in (owner_repo or ""):
        return {"ok": False, "error": "need owner/repo"}
    params = {"per_page": 5}
    if branch:
        params["branch"] = branch
    r = _get(f"/repos/{owner_repo}/actions/runs", params)
    if not r.get("ok"):
        return r
    runs = r.get("data", {}).get("workflow_runs", []) if isinstance(r.get("data"), dict) else []
    return {"ok": True, "runs": [
        {"name": x.get("name", ""), "branch": x.get("head_branch", ""),
         "status": x.get("status", ""), "conclusion": x.get("conclusion", ""),
         "at": (x.get("created_at", "") or "")[:10]} for x in runs]}


def repo_brief(owner_repo: str):
    """One-screen repo health for the agent: issues + CI in a single reply."""
    iss = issues(owner_repo, "open", 5)
    ci = ci_status(owner_repo)
    if not iss.get("ok"):
        return iss
    lines = [f"{owner_repo}: {len(iss['issues'])} open issues"]
    lines += [f"• #{i['number']} {i['title'][:70]}" for i in iss["issues"][:5]]
    if ci.get("ok") and ci["runs"]:
        latest = ci["runs"][0]
        lines.append(f"CI: {latest['name']} {latest['conclusion'] or latest['status']} ({latest['branch']})")
    elif not ci.get("ok"):
        lines.append(f"CI: {ci.get('error', 'n/a')}")
    return {"ok": True, "reply": "\n".join(lines),
            "issues": iss["issues"], "ci": ci.get("runs", [])}
