"""
Bot と Webサイトの両方から使う共有データベース処理。
SQLite (data/verify.db) に以下を保存する:
  - guild_settings: サーバーごとの「付与するロール一覧」「ログ送信先チャンネルID」
  - verify_logs: 認証試行ログ(ユーザー名・ID・IPアドレス・結果・日時)
"""

import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "verify.db")
DB_PATH = os.path.abspath(DB_PATH)


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS guild_roles (
                guild_id TEXT NOT NULL,
                role_id TEXT NOT NULL,
                PRIMARY KEY (guild_id, role_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id TEXT PRIMARY KEY,
                log_channel_id TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS verify_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                username TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                success INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS verified_users (
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                verified_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


# ---------- ロール設定 ----------

def add_role(guild_id: str, role_id: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO guild_roles (guild_id, role_id) VALUES (?, ?)",
            (str(guild_id), str(role_id)),
        )
        conn.commit()


def remove_role(guild_id: str, role_id: str):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM guild_roles WHERE guild_id = ? AND role_id = ?",
            (str(guild_id), str(role_id)),
        )
        conn.commit()


def get_roles(guild_id: str) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role_id FROM guild_roles WHERE guild_id = ?",
            (str(guild_id),),
        ).fetchall()
        return [r[0] for r in rows]


# ---------- ログ送信先チャンネル ----------

def set_log_channel(guild_id: str, channel_id: str):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO guild_settings (guild_id, log_channel_id) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET log_channel_id = excluded.log_channel_id
            """,
            (str(guild_id), str(channel_id)),
        )
        conn.commit()


def get_log_channel(guild_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT log_channel_id FROM guild_settings WHERE guild_id = ?",
            (str(guild_id),),
        ).fetchone()
        return row[0] if row else None


# ---------- 認証済みユーザー管理 ----------

def mark_verified(guild_id: str, user_id: str, ip_address: str):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO verified_users (guild_id, user_id, ip_address, verified_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                ip_address = excluded.ip_address,
                last_seen_at = excluded.last_seen_at
            """,
            (
                str(guild_id), str(user_id), ip_address,
                datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()


def is_verified(guild_id: str, user_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM verified_users WHERE guild_id = ? AND user_id = ?",
            (str(guild_id), str(user_id)),
        ).fetchone()
        return row is not None


def get_distinct_users_for_ip(guild_id: str, ip_address: str, exclude_user_id: str | None = None) -> list[str]:
    """同じサーバー内で、このIPアドレスから過去に認証した(別の)ユーザーID一覧を返す。
    多重アカウント/荒らし検知用。"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT user_id FROM verified_users WHERE guild_id = ? AND ip_address = ?",
            (str(guild_id), ip_address),
        ).fetchall()
        ids = [r[0] for r in rows]
        if exclude_user_id is not None:
            ids = [i for i in ids if i != str(exclude_user_id)]
        return ids


# ---------- 認証ログ ----------

def add_verify_log(guild_id: str, user_id: str, username: str, ip_address: str, success: bool):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO verify_logs (guild_id, user_id, username, ip_address, success, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(guild_id),
                str(user_id),
                username,
                ip_address,
                1 if success else 0,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
