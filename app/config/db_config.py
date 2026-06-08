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
        return cls(
            host=os.getenv("AWT_DB_HOST", "localhost"),
            port=int(os.getenv("AWT_DB_PORT", "5432")),
            dbname=os.getenv("AWT_DB_NAME", "awt"),
            user=os.getenv("AWT_DB_USER", "awt_user"),
            password=os.getenv("AWT_DB_PASSWORD", ""),
        )

    def dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.dbname} "
            f"user={self.user} password={self.password}"
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
