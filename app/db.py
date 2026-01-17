import os
import sqlite3
from typing import Iterable, Optional


DB_PATH = os.path.join(os.path.dirname(__file__), "data.sqlite3")


def get_conn() -> sqlite3.Connection:
	conn = sqlite3.connect(DB_PATH, check_same_thread=False)
	conn.row_factory = sqlite3.Row
	return conn


def init_db() -> None:
	conn = get_conn()
	try:
		# Enable WAL mode for better concurrency
		conn.execute("PRAGMA journal_mode=WAL;")
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
		conn.commit()
	finally:
		conn.close()


def query_all(sql: str, params: Iterable = ()):
	conn = get_conn()
	try:
		cur = conn.execute(sql, params)
		return [dict(row) for row in cur.fetchall()]
	finally:
		conn.close()


def execute(sql: str, params: Iterable = ()) -> None:
	conn = get_conn()
	try:
		conn.execute(sql, params)
		conn.commit()
	finally:
		conn.close()


def query_one(sql: str, params: Iterable = ()) -> Optional[dict]:
	conn = get_conn()
	try:
		cur = conn.execute(sql, params)
		row = cur.fetchone()
		return dict(row) if row else None
	finally:
		conn.close()


