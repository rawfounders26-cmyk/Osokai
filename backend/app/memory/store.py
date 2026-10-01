"""Shared memory tables helper. All memory/* modules connect through here."""
import os
import time

try:
    from app.db import connect as _hardb
    from app.paths import data as _pdata
except ImportError:
    from db import connect as _hardb
    from paths import data as _pdata

DB = _pdata("osokai.db")


def db():
    conn = _hardb(os.path.normpath(DB))
    conn.execute("""CREATE TABLE IF NOT EXISTS mem_people(
        id INTEGER PRIMARY KEY, name TEXT, relation TEXT DEFAULT '',
        notes TEXT DEFAULT '', ts REAL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS mem_places(
        id INTEGER PRIMARY KEY, name TEXT, kind TEXT DEFAULT '',
        notes TEXT DEFAULT '', ts REAL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS mem_episodes(
        id INTEGER PRIMARY KEY, text TEXT, importance REAL DEFAULT 1.0, ts REAL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS mem_routines(
        id INTEGER PRIMARY KEY, name TEXT, steps TEXT DEFAULT '[]',
        times_used INT DEFAULT 0, ts REAL)""")
    return conn


def now() -> float:
    return time.time()
