"""PostgreSQL 중앙 인증 클라이언트 (D40, D44)."""
from __future__ import annotations
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import psycopg2
import psycopg2.extras

from app.config.db_config import DBConfig

_SESSION_TTL_HOURS = 8
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS awt_users (
    user_id     SERIAL PRIMARY KEY,
    username    VARCHAR(64) UNIQUE NOT NULL,
    pw_hash     CHAR(64) NOT NULL,       -- SHA-256 hex
    role        VARCHAR(16) NOT NULL DEFAULT 'reviewer',  -- reviewer | admin
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS awt_sessions (
    token       CHAR(64) PRIMARY KEY,    -- SHA-256 hex of random bytes
    user_id     INT NOT NULL REFERENCES awt_users(user_id) ON DELETE CASCADE,
    username    VARCHAR(64) NOT NULL,
    role        VARCHAR(16) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_expires ON awt_sessions(expires_at);

CREATE TABLE IF NOT EXISTS awt_asset_events (
    event_id    SERIAL PRIMARY KEY,
    asset_type  VARCHAR(32)  NOT NULL,   -- 'defect' | 'invariant' | 'pattern'
    asset_id    VARCHAR(64)  NOT NULL,   -- 'DEF-2026-BRD-001'
    action      VARCHAR(32)  NOT NULL,   -- 'created' | 'pattern_approved' | 'rejected' | 'archived'
    actor_id    INT REFERENCES awt_users(user_id) ON DELETE SET NULL,
    actor_name  VARCHAR(64),             -- 비정규화 (계정 삭제 후도 이력 유지)
    note        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_asset_events_asset  ON awt_asset_events(asset_type, asset_id);
CREATE INDEX IF NOT EXISTS idx_asset_events_actor  ON awt_asset_events(actor_id);
"""


def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _hash_token(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class DBClient:
    """AWT 사용자 인증 + 세션 관리."""

    def __init__(self, config: DBConfig | None = None):
        self._cfg = config or DBConfig.from_env()
        self._conn: psycopg2.extensions.connection | None = None

    # ── 연결 ─────────────────────────────────────────────────────────────
    def connect(self) -> None:
        self._conn = psycopg2.connect(**self._cfg.connect_kwargs())
        self._conn.autocommit = False

    def close(self) -> None:
        if self._conn and not self._conn.closed:
            self._conn.close()
        self._conn = None

    def __enter__(self) -> "DBClient":
        self.connect()
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def _cur(self) -> psycopg2.extras.DictCursor:
        if not self._conn or self._conn.closed:
            self.connect()
        return self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # ── 스키마 초기화 ─────────────────────────────────────────────────────
    def ensure_schema(self) -> None:
        with self._cur() as cur:
            cur.execute(_SCHEMA_SQL)
        self._conn.commit()

    # ── 사용자 관리 ──────────────────────────────────────────────────────
    def create_user(self, username: str, password: str, role: str = "reviewer") -> int:
        """새 사용자 생성. user_id 반환. 중복 시 ValueError."""
        if role not in ("reviewer", "admin"):
            raise ValueError(f"Invalid role: {role}")
        pw_hash = _hash_pw(password)
        try:
            with self._cur() as cur:
                cur.execute(
                    "INSERT INTO awt_users (username, pw_hash, role) VALUES (%s, %s, %s) RETURNING user_id",
                    (username, pw_hash, role),
                )
                user_id = cur.fetchone()[0]
            self._conn.commit()
            return user_id
        except psycopg2.errors.UniqueViolation:
            self._conn.rollback()
            raise ValueError(f"Username already exists: {username}")

    def change_password(self, username: str, new_password: str) -> bool:
        pw_hash = _hash_pw(new_password)
        with self._cur() as cur:
            cur.execute(
                "UPDATE awt_users SET pw_hash=%s WHERE username=%s",
                (pw_hash, username),
            )
            updated = cur.rowcount
        self._conn.commit()
        return updated > 0

    def list_users(self) -> list[dict]:
        with self._cur() as cur:
            cur.execute("SELECT user_id, username, role, created_at FROM awt_users ORDER BY user_id")
            return [dict(r) for r in cur.fetchall()]

    def delete_user(self, username: str) -> bool:
        with self._cur() as cur:
            cur.execute("DELETE FROM awt_users WHERE username=%s", (username,))
            deleted = cur.rowcount
        self._conn.commit()
        return deleted > 0

    # ── 인증 + 세션 ──────────────────────────────────────────────────────
    def login(self, username: str, password: str) -> str | None:
        """인증 성공 시 세션 토큰 반환. 실패 시 None."""
        pw_hash = _hash_pw(password)
        with self._cur() as cur:
            cur.execute(
                "SELECT user_id, role FROM awt_users WHERE username=%s AND pw_hash=%s",
                (username, pw_hash),
            )
            row = cur.fetchone()
        if not row:
            return None

        user_id, role = row["user_id"], row["role"]
        raw_token = secrets.token_bytes(32)
        token = _hash_token(raw_token)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=_SESSION_TTL_HOURS)

        with self._cur() as cur:
            # 기존 만료 세션 정리
            cur.execute("DELETE FROM awt_sessions WHERE expires_at < %s", (now,))
            cur.execute(
                "INSERT INTO awt_sessions (token, user_id, username, role, created_at, expires_at) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (token, user_id, username, role, now, expires_at),
            )
        self._conn.commit()
        return token

    def validate_session(self, token: str) -> dict | None:
        """유효한 세션이면 {username, role, expires_at} 반환. 무효면 None."""
        now = datetime.now(timezone.utc)
        with self._cur() as cur:
            cur.execute(
                "SELECT username, role, expires_at FROM awt_sessions "
                "WHERE token=%s AND expires_at > %s",
                (token, now),
            )
            row = cur.fetchone()
        if not row:
            return None
        return dict(row)

    def logout(self, token: str) -> None:
        with self._cur() as cur:
            cur.execute("DELETE FROM awt_sessions WHERE token=%s", (token,))
        self._conn.commit()

    def purge_expired_sessions(self) -> int:
        now = datetime.now(timezone.utc)
        with self._cur() as cur:
            cur.execute("DELETE FROM awt_sessions WHERE expires_at < %s", (now,))
            count = cur.rowcount
        self._conn.commit()
        return count

    # ── 헬퍼 ─────────────────────────────────────────────────────────────
    @staticmethod
    def is_available(config: DBConfig | None = None) -> bool:
        """DB 접속 가능 여부 확인 (로그인 화면 전 probe)."""
        cfg = config or DBConfig.from_env()
        try:
            conn = psycopg2.connect(dsn=cfg.dsn(), connect_timeout=3)
            conn.close()
            return True
        except Exception:
            return False
