"""RAG — ingest workspace docs, full-text search (SQLite FTS5, zero deps),
retrieve-then-synthesize answers with citations. Vector embeddings later."""
import os
import re
import sqlite3

DB = os.path.join(os.path.dirname(__file__), "..", "porter_local.db")
try:
    WS = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "workspace"))
except Exception:
    WS = "workspace"

TEXT_EXTS = (".md", ".txt", ".py", ".js", ".json", ".csv", ".html")


def _db():
    db = sqlite3.connect(os.path.normpath(DB), check_same_thread=False)
    db.execute("CREATE TABLE IF NOT EXISTS rag_docs(path TEXT PRIMARY KEY, mtime REAL)")
    db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS rag_fts USING fts5(path, chunk)")
    return db


def _chunks(text: str, size: int = 1200):
    text = re.sub(r"\s+", " ", text)
    return [text[i:i + size] for i in range(0, len(text), size) if text[i:i + size].strip()]


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
    db = _db()
    try:
        rows = db.execute(
            "SELECT path, snippet(rag_fts, 1, '[', ']', '…', 12) FROM rag_fts "
            "WHERE rag_fts MATCH ? LIMIT ?", (query, k)).fetchall()
    except Exception:
        return []
    return [{"path": r[0], "snippet": r[1]} for r in rows]


def stats():
    db = _db()
    return {"docs": db.execute("SELECT COUNT(*) FROM rag_docs").fetchone()[0],
            "chunks": db.execute("SELECT COUNT(*) FROM rag_fts").fetchone()[0]}
