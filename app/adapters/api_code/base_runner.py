"""언어별 러너 공통 계약 + 기법 기반 인자 합성 (D62).

Runner는 두 가지만 한다:
  list_symbols(target_config) → [Symbol]   (리플렉션/명세 파싱)
  invoke(symbol, args, kwargs, target_config) → {ok, return, exception, message}

인자 합성(synth_call)은 언어 무관 — 파라미터의 annotation '문자열 타입명'으로 값 생성.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class Symbol:
    symbol: str                       # 맵 키 = TC 소분류 (예: "add", "Calculator.add")
    name: str                         # 호출 대상 이름
    signature: str = ""
    doc: str = ""
    params: list[dict] = field(default_factory=list)  # {name,annotation,required,default,kind}
    returns: str = ""
    raises: list[str] = field(default_factory=list)
    qualname: str = ""                # 런타임 getattr 경로(클래스.메서드 등)


@runtime_checkable
class Runner(Protocol):
    lang: str
    def list_symbols(self, target_config: dict) -> list[Symbol]: ...
    def invoke(self, sym: Symbol, args: list, kwargs: dict,
               target_config: dict) -> dict: ...


# ── 타입명 → 값 합성 ─────────────────────────────────────────────────────────
def _ann(annotation: str) -> str:
    return (annotation or "").lower()


def valid_value(annotation: str) -> Any:
    a = _ann(annotation)
    if any(t in a for t in ("int", "long", "int32", "int64", "integer")) and "point" not in a:
        return 1
    if any(t in a for t in ("float", "double", "decimal", "number", "single")):
        return 1.0
    if "bool" in a:
        return True
    if any(t in a for t in ("list", "array", "[]", "sequence", "iterable")):
        return []
    if any(t in a for t in ("dict", "map", "object")):
        return {}
    if any(t in a for t in ("str", "string", "char", "text")):
        return "test"
    return "test"   # 미지정/미상 → 보수적 기본값


def wrong_value(annotation: str) -> Any:
    """타입 위반 값(validation 시험). 숫자엔 문자열, 문자열엔 객체."""
    a = _ann(annotation)
    if any(t in a for t in ("int", "long", "float", "double", "number", "decimal")):
        return "NOT_A_NUMBER"
    if "bool" in a:
        return "NOT_A_BOOL"
    if any(t in a for t in ("str", "string", "char", "text")):
        return object()
    return object()


def boundary_value(annotation: str) -> Any:
    a = _ann(annotation)
    if any(t in a for t in ("int", "long", "float", "double", "number")):
        return 2 ** 63
    if any(t in a for t in ("str", "string", "text")):
        return "x" * 100000
    return None


_POSITIVE_TECH = {"happy_path", "equivalence", "state_transition", "cross_feature"}


def synth_call(sym: Symbol, technique: str, negcat: str):
    """(kwargs, expect_exception) 또는 None(합성 불가).

    정상 기법 → 유효 인자(이름+타입 의미 반영), 예외 기대 없음.
    음성 기법 → 첫 필수 인자를 위반 값으로, 예외 기대.
    값 합성은 value_synth(이름/타입/format 휴리스틱)에 위임 — 매뉴얼 없이도 동작.
    """
    from app.adapters import value_synth

    required = [p for p in sym.params if p.get("required")]
    is_negative = technique not in _POSITIVE_TECH and technique != ""

    def _valid(p):
        return value_synth.valid_value(p["name"], p.get("annotation", ""))

    if not is_negative:
        return ({p["name"]: _valid(p) for p in required}, False)

    if not required:
        return None  # 인자 없는 함수는 음성 합성 불가 → 호출측에서 skip
    kw = {p["name"]: _valid(p) for p in required}
    first = required[0]
    if negcat == "boundary_violation":
        bv = value_synth.boundary_value(first["name"], first.get("annotation", ""))
        if bv is not None:
            kw[first["name"]] = bv
    else:  # validation_failure / injection 등 → 위반 값
        kw[first["name"]] = value_synth.invalid_value(
            first["name"], first.get("annotation", ""), None, negcat)
    return (kw, True)
