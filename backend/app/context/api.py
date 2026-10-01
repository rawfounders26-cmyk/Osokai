"""Context HTTP surface. Included into the main app with one line.
All app imports are lazy (function-level) to avoid circulars."""
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
    # standalone fallback (same token contract) when main isn't importable
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


@router.get("/context/events")
def ctx_events(etype: str = "", limit: int = 50, _=Depends(_auth_dep())):
    try:
        from app.context.events import list_events
    except ImportError:
        from context.events import list_events
    return {"events": list_events(etype, 0, limit)}


@router.post("/context/emit")
async def ctx_emit(payload: dict, _=Depends(_auth_dep())):
    try:
        from app.context.events import emit
    except ImportError:
        from context.events import emit
    r = emit(payload.get("type", ""), payload.get("payload", {}),
             payload.get("source", "client"), payload.get("actor", ""))
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("error", "bad event"))
    await _push()
    return r


@router.get("/context/snapshot")
def ctx_snapshot(_=Depends(_auth_dep())):
    try:
        from app.context.store import snapshot
    except ImportError:
        from context.store import snapshot
    return snapshot()


@router.get("/context/wake")
def wake_list(_=Depends(_auth_dep())):
    try:
        from app.context.wake import list_conditions
    except ImportError:
        from context.wake import list_conditions
    return {"conditions": list_conditions()}


@router.post("/context/wake")
async def wake_add(payload: dict, _=Depends(_auth_dep())):
    try:
        from app.context.wake import add
    except ImportError:
        from context.wake import add
    r = add(payload.get("name", "wake"), payload.get("event", ""),
            payload.get("action", "nudge"), payload.get("match", {}), payload.get("args", {}))
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("error", "bad condition"))
    await _push()
    return r


@router.post("/context/wake/{cid}/enable")
async def wake_enable(cid: int, payload: dict, _=Depends(_auth_dep())):
    try:
        from app.context.wake import set_enabled
    except ImportError:
        from context.wake import set_enabled
    r = set_enabled(cid, bool(payload.get("enabled", True)))
    await _push()
    return r


@router.delete("/context/wake/{cid}")
async def wake_delete(cid: int, _=Depends(_auth_dep())):
    try:
        from app.context.wake import remove
    except ImportError:
        from context.wake import remove
    r = remove(cid)
    await _push()
    return r
