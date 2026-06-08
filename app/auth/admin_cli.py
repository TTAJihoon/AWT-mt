"""AWT 관리자 CLI — DB 초기화 및 초기 admin 계정 생성.

사용법:
    python -m app.auth.admin_cli init           # 스키마 생성
    python -m app.auth.admin_cli create-user    # 대화형 사용자 추가
    python -m app.auth.admin_cli list-users     # 사용자 목록
"""
from __future__ import annotations
import getpass
import sys

from app.auth.db_client import DBClient
from app.config.db_config import DBConfig


def _client() -> DBClient:
    db = DBClient(DBConfig.from_env())
    db.connect()
    return db


def cmd_init() -> None:
    db = _client()
    db.ensure_schema()
    print("[OK] 스키마 초기화 완료.")
    db.close()


def cmd_create_user() -> None:
    db = _client()
    username = input("사용자명: ").strip()
    password = getpass.getpass("비밀번호: ")
    confirm = getpass.getpass("비밀번호 확인: ")
    if password != confirm:
        print("[ERROR] 비밀번호가 일치하지 않습니다.")
        db.close()
        return
    role = input("역할 (reviewer/admin) [reviewer]: ").strip() or "reviewer"
    try:
        uid = db.create_user(username, password, role)
        print(f"[OK] 사용자 생성: {username} (id={uid}, role={role})")
    except ValueError as e:
        print(f"[ERROR] {e}")
    db.close()


def cmd_list_users() -> None:
    db = _client()
    users = db.list_users()
    if not users:
        print("(사용자 없음)")
    for u in users:
        print(f"  {u['user_id']:3d}  {u['username']:<20}  {u['role']:<12}  {u['created_at']}")
    db.close()


_COMMANDS = {
    "init": cmd_init,
    "create-user": cmd_create_user,
    "list-users": cmd_list_users,
}


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in _COMMANDS:
        print(f"사용법: python -m app.auth.admin_cli [{' | '.join(_COMMANDS)}]")
        sys.exit(1)
    _COMMANDS[sys.argv[1]]()
