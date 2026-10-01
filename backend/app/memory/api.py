"""Memory HTTP surface. Included into the main app with one line.
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
    from fastapi import Request as _Req, Header as _Hdr, HTTPException as _HE
    import os as _os

    def _standalone(request: _Req, authorization: str = _Hdr(default="")):
        want = _os.getenv("OSOKAI_AUTH_TOKEN", "")
        if want and authorization != f"Bearer {want}":
            raise _HE(status_code=401, detail="bad token")
    return _standalone


def _mem():
    try:
        from app.memory import Memory
    except ImportError:
        from memory import Memory
    return Memory()


@router.post("/memory/people")
async def person_add(payload: dict, _=Depends(_auth_dep())):
    m = _mem()
    r = m.remember_person(payload.get("name", ""), payload.get("relation", ""), payload.get("notes", ""))
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("error", "bad person"))
    return r


@router.post("/memory/places")
async def place_add(payload: dict, _=Depends(_auth_dep())):
    m = _mem()
    r = m.remember_place(payload.get("name", ""), payload.get("kind", ""), payload.get("notes", ""))
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("error", "bad place"))
    return r


@router.get("/memory/recall-all")
def recall_all(q: str = "", k: int = 8, _=Depends(_auth_dep())):
    return {"results": _mem().recall_all(q[:200], k)}


@router.post("/memory/consolidate")
async def consolidate(_=Depends(_auth_dep())):
    return _mem().consolidate()


@router.post("/memory/confirm")
async def confirm(payload: dict, _=Depends(_auth_dep())):
    """Explicit feedback: this recalled memory was actually useful."""
    try:
        from memory.retrieval import confirm_useful
    except ImportError:
        from app.memory.retrieval import confirm_useful
    return confirm_useful(payload.get("text", ""))


@router.get("/memory/recall-explain")
def recall_explain(q: str = "", k: int = 8, _=Depends(_auth_dep())):
    try:
        from memory.retrieval import recall_all
    except ImportError:
        from app.memory.retrieval import recall_all
    return {"results": recall_all(q[:200], k, explain=True)}
