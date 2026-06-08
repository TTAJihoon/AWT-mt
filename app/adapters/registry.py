"""target_kind → TargetAdapter 레지스트리 (D59)."""
from __future__ import annotations

from typing import Callable

from app.adapters.base import TargetAdapter

_REGISTRY: dict[str, Callable[[], TargetAdapter]] = {}
_LABELS: dict[str, str] = {}


def register(kind: str, factory: Callable[[], TargetAdapter], label: str = "") -> None:
    """어댑터 팩토리 등록. 팩토리는 호출마다 새 TargetAdapter를 만든다(상태 격리)."""
    _REGISTRY[kind] = factory
    if label:
        _LABELS[kind] = label


def get_adapter(kind: str | None) -> TargetAdapter:
    kind = kind or "web"
    if kind not in _REGISTRY:
        raise ValueError(
            f"알 수 없는 target_kind: {kind!r}. 등록된 유형: {list(_REGISTRY)}"
        )
    return _REGISTRY[kind]()


def available_kinds() -> list[str]:
    return list(_REGISTRY)


def labels() -> dict[str, str]:
    return dict(_LABELS)
