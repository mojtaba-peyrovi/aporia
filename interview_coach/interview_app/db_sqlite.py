from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class UserRow:
    user_id: int
    email: str
    first_name: str
    last_name: str


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def _default_db_path() -> Path:
    base_dir = Path(__file__).resolve().parents[1]
    data_dir = base_dir / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "aporia.sqlite3"


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or _default_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_login_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def upsert_user(*, email: str, first_name: str, last_name: str, db_path: Path | None = None) -> int:
    now = _utc_now_iso()
    with _connect(db_path) as conn:
        _ensure_schema(conn)
        conn.execute(
            """
            INSERT INTO users (email, first_name, last_name, created_at, last_login_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                last_login_at=excluded.last_login_at
            """,
            (email, first_name, last_name, now, now),
        )
        row = conn.execute("SELECT user_id FROM users WHERE email=?", (email,)).fetchone()
        if not row:
            raise RuntimeError("Failed to load upserted user")
        return int(row["user_id"])

