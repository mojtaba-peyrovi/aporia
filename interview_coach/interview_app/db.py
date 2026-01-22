from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from os import getenv
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class MySQLConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def _default_sqlite_db_path() -> Path:
    base_dir = Path(__file__).resolve().parents[1]
    data_dir = base_dir / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "aporia.sqlite3"


def _load_mysql_config_from_env() -> MySQLConfig | None:
    host = getenv("MYSQL_HOST")
    database = getenv("MYSQL_DATABASE")
    user = getenv("MYSQL_USER")
    password = getenv("MYSQL_PASSWORD")
    port_str = getenv("MYSQL_PORT") or "3306"

    if not host:
        return None
    if not (database and user and password):
        raise RuntimeError(
            "MYSQL_HOST is set but MYSQL_DATABASE/MYSQL_USER/MYSQL_PASSWORD are missing; cannot connect to MySQL."
        )
    try:
        port = int(port_str)
    except ValueError as e:
        raise RuntimeError(f"Invalid MYSQL_PORT: {port_str!r}") from e
    return MySQLConfig(host=host, port=port, user=user, password=password, database=database)


def _connect_sqlite(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or _default_sqlite_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _ensure_schema_sqlite(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_login_at TEXT NOT NULL,
            profile_json TEXT,
            top_skills_json TEXT,
            cv_file_hash TEXT,
            cv_text TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vacancies (
            vacancy_id INTEGER PRIMARY KEY AUTOINCREMENT,
            position_title TEXT NOT NULL,
            jd_file_hash TEXT NOT NULL,
            jd_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(position_title, jd_file_hash)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_vacancies (
            user_vacancy_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            vacancy_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, vacancy_id),
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(vacancy_id) REFERENCES vacancies(vacancy_id)
        )
        """
    )
    conn.commit()


def _connect_mysql(cfg: MySQLConfig):
    try:
        import mysql.connector  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "MySQL is configured but mysql.connector is not installed. "
            "Install `mysql-connector-python` (recommended) or use the SQLite fallback."
        ) from e

    return mysql.connector.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        database=cfg.database,
        autocommit=True,
    )


def _ensure_schema_mysql(conn) -> None:  # pragma: no cover
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(320) NOT NULL UNIQUE,
            first_name VARCHAR(128) NOT NULL,
            last_name VARCHAR(128) NOT NULL,
            created_at DATETIME NOT NULL,
            last_login_at DATETIME NOT NULL,
            profile_json JSON NULL,
            top_skills_json JSON NULL,
            cv_file_hash VARCHAR(128) NULL,
            cv_text MEDIUMTEXT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vacancies (
            vacancy_id INT AUTO_INCREMENT PRIMARY KEY,
            position_title VARCHAR(255) NOT NULL,
            jd_file_hash VARCHAR(128) NOT NULL,
            jd_text MEDIUMTEXT NOT NULL,
            created_at DATETIME NOT NULL,
            UNIQUE KEY uq_vacancies_title_hash (position_title, jd_file_hash)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_vacancies (
            user_vacancy_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            vacancy_id INT NOT NULL,
            created_at DATETIME NOT NULL,
            UNIQUE KEY uq_user_vacancy (user_id, vacancy_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (vacancy_id) REFERENCES vacancies(vacancy_id)
        )
        """
    )
    cur.close()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def upsert_user_identity(
    *,
    email: str,
    first_name: str,
    last_name: str,
    sqlite_db_path: Path | None = None,
) -> int:
    mysql_cfg = _load_mysql_config_from_env()
    if mysql_cfg:
        conn = _connect_mysql(mysql_cfg)
        try:
            _ensure_schema_mysql(conn)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO users (email, first_name, last_name, created_at, last_login_at)
                VALUES (%s, %s, %s, NOW(), NOW())
                ON DUPLICATE KEY UPDATE
                    first_name=VALUES(first_name),
                    last_name=VALUES(last_name),
                    last_login_at=VALUES(last_login_at)
                """,
                (email, first_name, last_name),
            )
            cur.execute("SELECT user_id FROM users WHERE email=%s", (email,))
            row = cur.fetchone()
            if not row:
                raise RuntimeError("Failed to load upserted user")
            return int(row[0])
        finally:
            conn.close()

    now = _utc_now_iso()
    with _connect_sqlite(sqlite_db_path) as conn:
        _ensure_schema_sqlite(conn)
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


def update_user_cv(
    *,
    user_id: int,
    cv_file_hash: str,
    cv_text: str,
    sqlite_db_path: Path | None = None,
) -> None:
    mysql_cfg = _load_mysql_config_from_env()
    if mysql_cfg:
        conn = _connect_mysql(mysql_cfg)
        try:
            _ensure_schema_mysql(conn)
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET cv_file_hash=%s, cv_text=%s WHERE user_id=%s",
                (cv_file_hash, cv_text, user_id),
            )
            cur.close()
            return
        finally:
            conn.close()

    with _connect_sqlite(sqlite_db_path) as conn:
        _ensure_schema_sqlite(conn)
        conn.execute(
            "UPDATE users SET cv_file_hash=?, cv_text=? WHERE user_id=?",
            (cv_file_hash, cv_text, user_id),
        )


def update_user_profile(
    *,
    user_id: int,
    profile: dict[str, Any],
    top_skills: Iterable[str],
    sqlite_db_path: Path | None = None,
) -> None:
    profile_json = _json_dumps(profile)
    top_skills_json = _json_dumps(list(top_skills))

    mysql_cfg = _load_mysql_config_from_env()
    if mysql_cfg:
        conn = _connect_mysql(mysql_cfg)
        try:
            _ensure_schema_mysql(conn)
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET profile_json=%s, top_skills_json=%s WHERE user_id=%s",
                (profile_json, top_skills_json, user_id),
            )
            cur.close()
            return
        finally:
            conn.close()

    with _connect_sqlite(sqlite_db_path) as conn:
        _ensure_schema_sqlite(conn)
        conn.execute(
            "UPDATE users SET profile_json=?, top_skills_json=? WHERE user_id=?",
            (profile_json, top_skills_json, user_id),
        )


def upsert_vacancy(
    *,
    position_title: str,
    jd_file_hash: str,
    jd_text: str,
    sqlite_db_path: Path | None = None,
) -> int:
    if not position_title.strip():
        raise ValueError("position_title must be non-empty")

    mysql_cfg = _load_mysql_config_from_env()
    if mysql_cfg:
        conn = _connect_mysql(mysql_cfg)
        try:
            _ensure_schema_mysql(conn)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO vacancies (position_title, jd_file_hash, jd_text, created_at)
                VALUES (%s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                    jd_text=VALUES(jd_text)
                """,
                (position_title, jd_file_hash, jd_text),
            )
            cur.execute(
                "SELECT vacancy_id FROM vacancies WHERE position_title=%s AND jd_file_hash=%s",
                (position_title, jd_file_hash),
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError("Failed to load upserted vacancy")
            return int(row[0])
        finally:
            conn.close()

    now = _utc_now_iso()
    with _connect_sqlite(sqlite_db_path) as conn:
        _ensure_schema_sqlite(conn)
        conn.execute(
            """
            INSERT INTO vacancies (position_title, jd_file_hash, jd_text, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(position_title, jd_file_hash) DO UPDATE SET
                jd_text=excluded.jd_text
            """,
            (position_title, jd_file_hash, jd_text, now),
        )
        row = conn.execute(
            "SELECT vacancy_id FROM vacancies WHERE position_title=? AND jd_file_hash=?",
            (position_title, jd_file_hash),
        ).fetchone()
        if not row:
            raise RuntimeError("Failed to load upserted vacancy")
        return int(row["vacancy_id"])


def link_user_vacancy(
    *,
    user_id: int,
    vacancy_id: int,
    sqlite_db_path: Path | None = None,
) -> int:
    mysql_cfg = _load_mysql_config_from_env()
    if mysql_cfg:
        conn = _connect_mysql(mysql_cfg)
        try:
            _ensure_schema_mysql(conn)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO user_vacancies (user_id, vacancy_id, created_at)
                VALUES (%s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                    user_id=VALUES(user_id)
                """,
                (user_id, vacancy_id),
            )
            cur.execute(
                "SELECT user_vacancy_id FROM user_vacancies WHERE user_id=%s AND vacancy_id=%s",
                (user_id, vacancy_id),
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError("Failed to load user_vacancy link")
            return int(row[0])
        finally:
            conn.close()

    now = _utc_now_iso()
    with _connect_sqlite(sqlite_db_path) as conn:
        _ensure_schema_sqlite(conn)
        conn.execute(
            """
            INSERT INTO user_vacancies (user_id, vacancy_id, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, vacancy_id) DO UPDATE SET
                user_id=excluded.user_id
            """,
            (user_id, vacancy_id, now),
        )
        row = conn.execute(
            "SELECT user_vacancy_id FROM user_vacancies WHERE user_id=? AND vacancy_id=?",
            (user_id, vacancy_id),
        ).fetchone()
        if not row:
            raise RuntimeError("Failed to load user_vacancy link")
        return int(row["user_vacancy_id"])

