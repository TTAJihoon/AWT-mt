"""LLM 호출 결과 SHA-256 캐시 (D41)."""
import hashlib
import json
from pathlib import Path

CACHE_DIR = Path("data/llm_cache")


def _key(call_id: str, contract_version: str, inputs: dict) -> str:
    raw = call_id + contract_version + json.dumps(inputs, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def get(call_id: str, contract_version: str, inputs: dict) -> dict | None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{_key(call_id, contract_version, inputs)}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def put(call_id: str, contract_version: str, inputs: dict, result: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{_key(call_id, contract_version, inputs)}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
