"""Benchmark HTTP surface. Included into the main app with one line.
Plan mode runs offline (safe on every call); live mode is env-gated."""
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter()


def _auth_dep():
    try:
        from app.main import need_auth
        return need_auth
    except ImportError:
        pass
    try:
        from main import need_auth
        return need_auth
    except ImportError:
        pass
    from fastapi import Request as _Req, Header as _Hdr, HTTPException as _HE
    import os as _os

    def _standalone(request: _Req, authorization: str = _Hdr(default="")):
        want = _os.getenv("OSOKAI_AUTH_TOKEN", "")
        if want and authorization != f"Bearer {want}":
            raise _HE(status_code=401, detail="bad token")
    return _standalone


async def _push():
    try:
        try:
            from app.main import hub
        except ImportError:
            from main import hub
        await hub.push()
    except Exception:
        pass


@router.post("/benchmark/run")
async def bench_run(payload: dict = None, _=Depends(_auth_dep())):
    payload = payload or {}
    if payload.get("mode", "plan") == "live":
        try:
            from app.benchmark.run import run_live
        except ImportError:
            from benchmark.run import run_live
        r = run_live(int(payload.get("limit", 5)), payload.get("category", ""),
                     float(payload.get("max_cost_usd", 1.0)))
    else:
        try:
            from app.benchmark.run import run_plan
        except ImportError:
            from benchmark.run import run_plan
        r = run_plan(payload.get("category", ""))
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("error", "run failed"))
    await _push()
    return r


@router.get("/benchmark/history")
def bench_history(limit: int = 10, _=Depends(_auth_dep())):
    try:
        from app.benchmark.run import history
    except ImportError:
        from benchmark.run import history
    return {"runs": history(limit)}


@router.get("/benchmark/interventions")
def bench_interventions(limit: int = 20, _=Depends(_auth_dep())):
    try:
        from app.benchmark.run import interventions_per_goal
    except ImportError:
        from benchmark.run import interventions_per_goal
    return interventions_per_goal(limit)
