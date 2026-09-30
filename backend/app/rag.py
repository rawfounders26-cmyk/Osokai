"""RAG — ingest workspace docs, full-text search (SQLite FTS5, zero deps),
retrieve-then-synthesize answers with citations. Vector embeddings later."""
import os
import re
import sqlite3

try:
    from app.paths import data as _pdata, ws as _pws
except ImportError:
    from paths import data as _pdata, ws as _pws

DB = _pdata("osokai.db")
WS = _pws()

TEXT_EXTS = (".md", ".txt", ".py", ".js", ".json", ".csv", ".html")


def _db():
    db = sqlite3.connect(os.path.normpath(DB), check_same_thread=False)
    db.execute("CREATE TABLE IF NOT EXISTS rag_docs(path TEXT PRIMARY KEY, mtime REAL)")
    db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS rag_fts USING fts5(path, chunk)")
    return db


def _chunks(text: str, size: int = 1200, overlap: int = 200):
    """Overlapping windows — answers never lose context at chunk edges."""
    text = re.sub(r"\s+", " ", text)
    if len(text) <= size:
        return [text] if text.strip() else []
    out, i = [], 0
    step = max(1, size - overlap)
    while i < len(text):
        ch = text[i:i + size]
        if ch.strip():
            out.append(ch)
        if i + size >= len(text):
            break
        i += step
    return out


def ingest(sub: str = "") -> dict:
    """Index all text docs under workspace/[sub]. Re-indexes changed files only."""
    base = os.path.normpath(os.path.join(WS, sub))
    if not base.startswith(WS) or not os.path.isdir(base):
        return {"ok": False, "error": "bad path"}
    db = _db()
    files, chunks = 0, 0
    for root, _, fns in os.walk(base):
        for fn in fns:
            if not fn.lower().endswith(TEXT_EXTS):
                continue
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, WS)
            mt = os.path.getmtime(fp)
            row = db.execute("SELECT mtime FROM rag_docs WHERE path=?", (rel,)).fetchone()
            if row and row[0] >= mt:
                continue
            try:
                txt = open(fp, encoding="utf-8", errors="ignore").read()[:200000]
            except Exception:
                continue
            db.execute("DELETE FROM rag_fts WHERE path=?", (rel,))
            for ch in _chunks(txt):
                db.execute("INSERT INTO rag_fts(path, chunk) VALUES(?,?)", (rel, ch))
                chunks += 1
            db.execute("INSERT OR REPLACE INTO rag_docs(path, mtime) VALUES(?,?)", (rel, mt))
            files += 1
    db.commit()
    n = db.execute("SELECT COUNT(*) FROM rag_fts").fetchone()[0]
    return {"ok": True, "files": files, "new_chunks": chunks, "total_chunks": n}


def search(query: str, k: int = 5):
    """Hybrid rank: FTS5 BM25 + path/title boost + recency-neutral.
    Returns scored hits with stable citation ids (`path#rowid`)."""
    db = _db()
    terms = [t.lower() for t in re.findall(r"\w+", query)]
    match = " OR ".join(terms) if terms else query
    try:
        rows = db.execute(
            "SELECT rowid, path, snippet(rag_fts, 1, '[', ']', '…', 12), bm25(rag_fts) "
            "FROM rag_fts WHERE rag_fts MATCH ? LIMIT ?", (match, k * 3)).fetchall()
    except Exception:
        return []
    scored = []
    for rowid, path, snip, bm in rows:
        score = -(bm or 0)
        pl = path.lower()
        score += sum(2.0 for t in terms if t in pl)  # filename/title match wins
        score += sum(0.2 for t in terms if t in (snip or "").lower())
        scored.append((score, {"path": path, "snippet": snip,
                               "cite": f"{path}#{rowid}", "score": round(score, 2)}))
    scored.sort(key=lambda s: -s[0])
    return [s[1] for s in scored[:k]]


def answer(query: str, k: int = 5) -> dict:
    """Retrieve-then-synthesize: grounded reply with citations. Fail-soft."""
    hits = search(query, k)
    if not hits:
        return {"ok": True, "reply": "Nothing in your workspace matches that yet.", "citations": []}
    ctx = "\n\n".join(f"[{h['cite']}] {h['snippet']}" for h in hits)
    try:
        try:
            from app.grok_client import chat_with_grok
        except ImportError:
            from grok_client import chat_with_grok
        reply = chat_with_grok(
            "Answer using ONLY the context below; cite sources like [path#id]. "
            f"Question: {query}\n\nContext:\n{ctx}")
    except Exception:
        reply = "Here's what I found:\n" + "\n".join(f"- [{h['cite']}] {h['snippet']}" for h in hits)
    return {"ok": True, "reply": reply, "citations": [h["cite"] for h in hits]}


def stats():
    db = _db()
    return {"docs": db.execute("SELECT COUNT(*) FROM rag_docs").fetchone()[0],
            "chunks": db.execute("SELECT COUNT(*) FROM rag_fts").fetchone()[0]}
