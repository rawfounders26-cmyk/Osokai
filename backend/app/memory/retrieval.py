"""Unified retrieval: one query across facts, people, places, episodes.

Multi-factor scoring (our own design): salience, keyword hits, recency decay,
relationship closeness, goal relevance, confirmation history, source trust.
Returns ranked results with per-result factor breakdowns for tuning.
"""
import hashlib as _hl
import time as _time
try:
    from memory.store import db
except ImportError:
    from app.memory.store import db

# factor weights — tuned against our own battery, not anyone else's
W_HIT = 2.0
W_RECENCY = 1.0
W_GOAL = 1.5
W_CONFIRM = 0.5

RELATION_W = {"self": 1.6, "family": 1.5, "partner": 1.5, "friend": 1.2,
              "colleague": 1.0, "manager": 1.1, "": 1.0}

SOURCE_TRUST = {"person": 1.2, "fact": 1.0, "episode": 1.0, "place": 0.9}


def _goal_words():
    """Open goal titles as context — memories serving live goals rank higher."""
    try:
        try:
            from app import goaltrees as _gt
        except ImportError:
            import goaltrees as _gt
        words = set()
        for g in _gt.list_trees():
            if g.get("progress", 100) < 100:
                words.update(w for w in g.get("title", "").lower().split() if len(w) > 2)
        return words
    except Exception:
        return set()


def _confirm_boost(text: str) -> float:
    """Shadow-feedback weight: confirmed-useful memories float up."""
    try:
        h = _hl.sha256((text or "").encode()).hexdigest()[:32]
        r = db().execute("SELECT shown, confirmed FROM recall_feedback WHERE h=?", (h,)).fetchone()
        if not r:
            return 0.0
        shown, confirmed = r[0] or 0, r[1] or 0
        if shown <= 0:
            return 0.0
        return W_CONFIRM * (confirmed / shown) * min(1.0, shown / 5.0)
    except Exception:
        return 0.0


def _record_shown(texts) -> None:
    """Shadow mode: log exposures without changing behavior (yet)."""
    try:
        conn = db()
        for t in texts or []:
            h = _hl.sha256((t or "").encode()).hexdigest()[:32]
            conn.execute("INSERT INTO recall_feedback(h, shown, confirmed) VALUES(?,1,0) "
                         "ON CONFLICT(h) DO UPDATE SET shown=shown+1", (h,))
        conn.commit()
    except Exception:
        pass


def score_factors(text: str, base: float, ts: float, terms, goal_words,
                  relation: str = "", kind: str = "") -> dict:
    """Transparent factor breakdown — every ranking decision is explainable."""
    tl = (text or "").lower()
    hits = sum(1.0 for t in terms if t in tl)
    age_days = max(0, (_time.time() - (ts or 0)) / 86400)
    recency = -min(1.0, age_days / 90) * W_RECENCY
    goal_hit = sum(1.0 for t in terms if t in goal_words) if goal_words else 0.0
    return {
        "salience": round(base, 2),
        "keyword": round(hits * W_HIT, 2),
        "recency": round(recency, 2),
        "relation": round(RELATION_W.get((relation or "").lower(), 1.0) - 1.0, 2),
        "goal": round(min(2.0, goal_hit) * W_GOAL, 2),
        "confirm": round(_confirm_boost(text), 2),
        "trust": round(SOURCE_TRUST.get(kind, 1.0) - 1.0, 2),
    }


def _total(f: dict) -> float:
    return (f["salience"] + f["keyword"] + f["recency"] + f["relation"]
            + f["goal"] + f["confirm"] + f["trust"])


def recall_all(query: str = "", k: int = 8, explain: bool = False):
    terms = [t for t in (query or "").lower().split() if len(t) > 2]
    goal_words = _goal_words()
    out = []

    def _emit(text, base, ts, relation="", kind=""):
        tl = (text or "").lower()
        if terms and not any(t in tl for t in terms):
            return
        f = score_factors(text, base, ts, terms, goal_words, relation, kind)
        item = {"kind": kind, "text": text, "ts": ts}
        if explain:
            item["factors"] = f
        out.append((_total(f), item))

    try:
        for r in db().execute("SELECT id, fact, salience, ts FROM facts ORDER BY ts DESC LIMIT 100").fetchall():
            _emit(r[1], r[2], r[3], kind="fact")
    except Exception:
        pass
    try:
        for r in db().execute("SELECT id, name, relation, notes FROM mem_people ORDER BY id DESC LIMIT 100").fetchall():
            _emit(f"{r[1]} ({r[2]}): {r[3]}".strip(), 2.0, 0, relation=r[2], kind="person")
    except Exception:
        pass
    try:
        for r in db().execute("SELECT id, name, kind, notes FROM mem_places ORDER BY id DESC LIMIT 100").fetchall():
            _emit(f"{r[1]} ({r[2]}): {r[3]}".strip(), 1.5, 0, kind="place")
    except Exception:
        pass
    try:
        for r in db().execute("SELECT id, text, importance, ts FROM mem_episodes ORDER BY ts DESC LIMIT 100").fetchall():
            _emit(r[1], r[2], r[3], kind="episode")
    except Exception:
        pass
    out.sort(key=lambda x: -x[0])
    top = [o[1] for o in out[:max(1, min(30, k))]]
    _record_shown([t["text"] for t in top])
    return top


def confirm_useful(text: str) -> dict:
    """Explicit feedback: this recalled memory was actually useful."""
    try:
        h = _hl.sha256((text or "").encode()).hexdigest()[:32]
        conn = db()
        conn.execute("INSERT INTO recall_feedback(h, shown, confirmed) VALUES(?,1,1) "
                     "ON CONFLICT(h) DO UPDATE SET confirmed=confirmed+1", (h,))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)[:150]}
