import os
import sqlite3
import threading
from typing import Iterable, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "data.sqlite3")

# Persistent connection to avoid open/close overhead on Windows
_CONN: Optional[sqlite3.Connection] = None
_LOCK = threading.Lock()

def get_conn() -> sqlite3.Connection:
    global _CONN
    with _LOCK:
        if _CONN is None:
            _CONN = sqlite3.connect(DB_PATH, check_same_thread=False)
            _CONN.row_factory = sqlite3.Row
            # WAL mode usually persistent, but setting it here again is fine
            _CONN.execute("PRAGMA journal_mode=WAL;")
    return _CONN

def init_db() -> None:
    # Ensure tables invoke get_conn which creates the connection
    conn = get_conn()
    with _LOCK:
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS pins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL UNIQUE,
                    created_at INTEGER NOT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS shares (
                    token TEXT PRIMARY KEY,
                    root TEXT NOT NULL,
                    readonly INTEGER NOT NULL,
                    allow_download INTEGER NOT NULL,
                    allow_edit INTEGER NOT NULL,
                    expires_at REAL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    script TEXT NOT NULL,
                    status TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    exit_code INTEGER,
                    log TEXT
                );
                """
            )
            conn.commit()
        except Exception as e:
            print(f"DB Init Error: {e}")

def query_all(sql: str, params: Iterable = ()):
    conn = get_conn()
    with _LOCK:
        cur = conn.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]

def execute(sql: str, params: Iterable = ()) -> None:
    conn = get_conn()
    with _LOCK:
        conn.execute(sql, params)
        conn.commit()

def query_one(sql: str, params: Iterable = ()) -> Optional[dict]:
    conn = get_conn()
    with _LOCK:
        cur = conn.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None
