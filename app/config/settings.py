"""API 키 + 활성 provider Fernet 암호화 저장/로드 (D42, D48).

저장 데이터 구조:
    {
        "active_provider": "anthropic" | "openai" | "google",
        "anthropic_key": "...",
        "openai_key": "...",
        "google_key": "..."
    }

기존 단일 키 형태 {"api_key": "..."}는 자동 마이그레이션 (anthropic_key로 이동).
"""
import os
import json
import hashlib
import platform
from pathlib import Path
from cryptography.fernet import Fernet

try:
    import sys
    from dotenv import load_dotenv
    if getattr(sys, "frozen", False):
        _env_path = Path(sys.executable).parent / ".env"
    else:
        _env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

_CONFIG_DIR = Path.home() / ".awt"
_CONFIG_FILE = _CONFIG_DIR / "settings.enc"

VALID_PROVIDERS = ("anthropic", "openai", "google")
_DEFAULT_PROVIDER = "anthropic"

# provider 이름 → 저장 키
_KEY_FIELD = {
    "anthropic": "anthropic_key",
    "openai": "openai_key",
    "google": "google_key",
}

# provider별 기본 모델 (사용자가 설정 탭에서 변경 가능)
DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-sonnet-4-6",
    "openai":    "gpt-4o",
    "google":    "gemini-2.5-flash",
}


def _machine_key() -> bytes:
    """머신 고유값(MAC + hostname)으로 32바이트 Fernet 키 파생."""
    import uuid
    raw = f"{uuid.getnode()}-{platform.node()}-awt-v1"
    digest = hashlib.sha256(raw.encode()).digest()
    import base64
    return base64.urlsafe_b64encode(digest)


def _fernet() -> Fernet:
    return Fernet(_machine_key())


def _load_payload() -> dict:
    """저장된 settings dict 로드. 없거나 깨졌으면 빈 dict 반환."""
    if not _CONFIG_FILE.exists():
        return {}
    try:
        decrypted = _fernet().decrypt(_CONFIG_FILE.read_bytes())
        data = json.loads(decrypted)
        # 구 형식 마이그레이션: {"api_key": "..."} → anthropic_key
        if "api_key" in data and "anthropic_key" not in data:
            data["anthropic_key"] = data.pop("api_key")
        return data
    except Exception:
        return {}


def _save_payload(payload: dict) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    encrypted = _fernet().encrypt(json.dumps(payload).encode())
    _CONFIG_FILE.write_bytes(encrypted)


# ── Public API ──────────────────────────────────────────────────────────

def get_active_provider() -> str:
    """현재 활성 provider 이름. .env의 LLM_PROVIDER가 있으면 그쪽 우선."""
    env = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if env in VALID_PROVIDERS:
        return env
    data = _load_payload()
    p = data.get("active_provider", _DEFAULT_PROVIDER)
    return p if p in VALID_PROVIDERS else _DEFAULT_PROVIDER


def set_active_provider(provider: str) -> None:
    """활성 provider 전환. 키는 그대로 보존.

    중요: .env의 LLM_PROVIDER는 '시작 시 기본값'일 뿐, 사용자가 UI에서 명시적으로
    전환하면 그 선택이 이번 세션에서 우선해야 한다. get_active_provider()가
    os.environ을 최우선으로 읽으므로, 여기서 os.environ도 함께 갱신해
    UI 전환이 즉시 반영되게 한다.
    """
    if provider not in VALID_PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}. Use one of {VALID_PROVIDERS}")
    data = _load_payload()
    data["active_provider"] = provider
    _save_payload(data)
    # .env 기본값을 덮어써 UI 선택이 우선되도록 (현재 프로세스 한정)
    os.environ["LLM_PROVIDER"] = provider


_ENV_KEY_VAR = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai":    "OPENAI_API_KEY",
    "google":    "GOOGLE_API_KEY",
}


def save_api_key(api_key: str, provider: str | None = None) -> None:
    """provider의 API 키 저장. provider 미지정 시 현재 활성 provider에 저장."""
    provider = provider or get_active_provider()
    if provider not in VALID_PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    data = _load_payload()
    data[_KEY_FIELD[provider]] = api_key
    # 활성 provider도 갱신 (UI에서 키 저장은 보통 그 provider를 쓴다는 의미)
    data["active_provider"] = provider
    _save_payload(data)
    # 환경변수도 즉시 갱신 — 기존 시스템 환경변수가 우선순위를 빼앗지 못하도록
    os.environ[_ENV_KEY_VAR[provider]] = api_key
    os.environ["LLM_PROVIDER"] = provider


def load_api_key(provider: str | None = None) -> str | None:
    """provider의 API 키 로드. provider 미지정 시 현재 활성 provider 키 반환.

    우선순위: UI 저장(암호화 파일) > 환경변수(.env / 시스템)
    UI에서 저장한 키가 항상 우선 적용된다. 재시작 후에도 유지됨.
    환경변수는 UI 저장 키가 없을 때만 폴백으로 사용.
    """
    provider = provider or get_active_provider()
    if provider not in VALID_PROVIDERS:
        return None

    # 1순위: UI에서 저장한 암호화 파일 (재시작 후에도 유지)
    data = _load_payload()
    stored = data.get(_KEY_FIELD[provider])
    if stored:
        return stored

    # 2순위: 환경변수 폴백 (.env 또는 시스템 환경변수)
    env_var = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
    }[provider]
    return os.environ.get(env_var, "").strip() or None


def get_provider_model(provider: str | None = None) -> str:
    """provider의 기본 모델 반환. 사용자가 저장한 값 우선, 없으면 내장 기본값."""
    provider = provider or get_active_provider()
    data = _load_payload()
    return data.get(f"{provider}_model") or DEFAULT_MODELS.get(provider, "")


def set_provider_model(provider: str, model: str) -> None:
    """provider의 기본 모델 저장."""
    if provider not in VALID_PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    data = _load_payload()
    data[f"{provider}_model"] = model
    _save_payload(data)


def delete_api_key(provider: str | None = None) -> None:
    """provider의 API 키만 삭제. 다른 provider 키와 active_provider는 보존."""
    provider = provider or get_active_provider()
    if provider not in VALID_PROVIDERS:
        return
    data = _load_payload()
    data.pop(_KEY_FIELD[provider], None)
    _save_payload(data)
    # 환경변수에서도 제거
    os.environ.pop(_ENV_KEY_VAR.get(provider, ""), None)


# ── 중앙 DB 접속 설정 (클라이언트 첫 실행 입력, D44/D59) ─────────────────────
# 분산 .exe 클라이언트가 중앙 PostgreSQL에 접속하기 위한 설정.
# 우선순위: UI 저장(암호화 파일) > 환경변수(.env) > 기본값.
_DB_FIELDS = ("host", "port", "dbname", "user", "password")
_DB_DEFAULTS = {"host": "localhost", "port": 5432, "dbname": "awt",
                "user": "awt_user", "password": ""}


def get_db_settings() -> dict:
    """저장된 DB 접속 설정(없으면 빈 dict)."""
    return dict(_load_payload().get("db_settings") or {})


def save_db_settings(settings: dict) -> None:
    """DB 접속 설정 저장(머신 고유값 Fernet 암호화)."""
    data = _load_payload()
    cur = dict(data.get("db_settings") or {})
    for k in _DB_FIELDS:
        if k in settings:
            cur[k] = settings[k]
    data["db_settings"] = cur
    _save_payload(data)


def has_db_settings() -> bool:
    """첫 실행 여부 판단 — DB host가 어디든 설정돼 있으면 완료로 본다.

    설치 마법사(awt_setup.iss)가 .env에 AWT_DB_HOST를 기록하면 인앱 첫 실행
    다이얼로그를 띄우지 않도록, 암호화 저장값 또는 환경변수 중 하나만 있어도 True.
    """
    if (_load_payload().get("db_settings") or {}).get("host"):
        return True
    return bool(os.getenv("AWT_DB_HOST", "").strip())


def effective_db_settings() -> dict:
    """저장값 > 환경변수 > 기본값 병합한 최종 접속 설정."""
    merged = dict(_DB_DEFAULTS)
    merged["host"] = os.getenv("AWT_DB_HOST", merged["host"])
    merged["port"] = int(os.getenv("AWT_DB_PORT", merged["port"]))
    merged["dbname"] = os.getenv("AWT_DB_NAME", merged["dbname"])
    merged["user"] = os.getenv("AWT_DB_USER", merged["user"])
    merged["password"] = os.getenv("AWT_DB_PASSWORD", merged["password"])
    for k, v in get_db_settings().items():
        if k in _DB_FIELDS and v != "":
            merged[k] = v
    merged["port"] = int(merged["port"])
    return merged
