"""PostgreSQL 접속 설정 (D44)."""
import os
from dataclasses import dataclass
from pathlib import Path

try:
    import sys
    from dotenv import load_dotenv
    # PyInstaller exe: AWT.exe 옆의 .env / 개발: 프로젝트 루트 .env
    if getattr(sys, "frozen", False):
        _env_path = Path(sys.executable).parent / ".env"
    else:
        _env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass


@dataclass
class DBConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> "DBConfig":
        # 우선순위: UI 저장 설정 > 환경변수 > 기본값 (settings.effective_db_settings)
        try:
            from app.config.settings import effective_db_settings
            s = effective_db_settings()
            return cls(host=s["host"], port=int(s["port"]), dbname=s["dbname"],
                       user=s["user"], password=s["password"])
        except Exception:
            return cls(
                host=os.getenv("AWT_DB_HOST", "localhost"),
                port=int(os.getenv("AWT_DB_PORT", "5432")),
                dbname=os.getenv("AWT_DB_NAME", "awt"),
                user=os.getenv("AWT_DB_USER", "awt_user"),
                password=os.getenv("AWT_DB_PASSWORD", ""),
            )

    # 한국어 Windows PostgreSQL은 오류 메시지를 CP949로 보내 psycopg2가 UTF-8
    # 디코딩에 실패(UnicodeDecodeError)할 수 있다. 이는 db_client.connect()에서
    # 원본 바이트를 CP949로 디코딩해 처리한다(서버 lc_messages를 건드리지 않음 —
    # lc_messages는 슈퍼유저만 설정 가능해 일반 계정 연결을 막기 때문).

    def dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.dbname} "
            f"user={self.user} password={self.password} client_encoding=UTF8"
        )

    def connect_kwargs(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
            "password": self.password,
            "client_encoding": "UTF8",
        }
