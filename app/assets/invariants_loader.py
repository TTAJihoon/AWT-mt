"""domain-invariants YAML 로더 — LLM 입력 주입용."""
from __future__ import annotations
from pathlib import Path

try:
    import yaml
    _YAML_OK = True
except ImportError:
    _YAML_OK = False

_ASSETS_DIR = Path(__file__).parent.parent.parent / "data" / "assets"
_INVARIANTS_DIR = _ASSETS_DIR / "domain-invariants"


def load_invariants(product_type_id: str) -> list[dict]:
    """지정 제품 유형의 invariants를 반환. yaml 없거나 pyyaml 미설치 시 빈 리스트."""
    if not _YAML_OK:
        return []
    yaml_path = _INVARIANTS_DIR / f"{product_type_id}.yaml"
    if not yaml_path.exists():
        return []
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    return [inv for inv in (raw or []) if inv.get("status") == "approved"]


def load_invariants_multi(product_type_ids: list[str]) -> list[dict]:
    """여러 제품 유형의 invariants를 합쳐서 반환 (중복 name 제거)."""
    seen: set[str] = set()
    result: list[dict] = []
    for ptype in product_type_ids:
        for inv in load_invariants(ptype):
            if inv["name"] not in seen:
                seen.add(inv["name"])
                result.append(inv)
    return result


def format_for_llm(
    invariants: list[dict],
    feature_type: str | None = None,
    max_chars: int = 2000,
) -> str:
    """LLM 입력용 텍스트로 변환. feature_type으로 필터링.

    source_quote 3단계 중 'invariants' 출처 근거가 되는 텍스트.
    """
    filtered = invariants
    if feature_type:
        filtered = [
            inv for inv in invariants
            if not inv.get("appliesTo") or feature_type in inv.get("appliesTo", [])
        ]
    if not filtered:
        return ""

    lines: list[str] = []
    for inv in filtered:
        lines.append(f"[{inv['name']}] {inv['statement']}")
        if inv.get("verification"):
            lines.append(f"  검증방법: {inv['verification']}")
        lines.append("")

    text = "\n".join(lines).strip()
    return text[:max_chars] if len(text) > max_chars else text
