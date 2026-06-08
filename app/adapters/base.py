"""대상 유형 플러그인 인터페이스 (D59).

AWT 코어(Stage 1~4,6,7)는 제품 무관이다. 웹에 묶인 Stage 0(구조 스캔)과
Stage 5(자동 실행)만 대상 유형별로 분기한다. 이 모듈은 그 분기점의
공통 계약(Protocol)을 정의한다.

원칙: 인터페이스는 얇게, 구현은 어댑터 내부에 두껍게.
  - GUI의 OCR/팝업/플레이키 처리, API의 status/schema 비교는 각 어댑터에 격리.
  - leaf/TC dict는 공통 계약(P1 동결·P2 추적성)이므로 코어는 불변.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Protocol, runtime_checkable

ProgressCb = Callable[[str], None]
StopFn = Callable[[], bool]


@dataclass
class Verdict:
    """OracleVerifier 판정 결과."""
    status: str                       # pass | fail | blocked | not_executed
    confidence: float = 0.5
    actual: str = ""
    evidence: list[str] = field(default_factory=list)


@runtime_checkable
class Probe(Protocol):
    """Stage 0 대체 — 대상 구조를 스캔해 feature_spec(dict)을 반환.

    반환 형태는 기존 stage0_dom_scan.scan 과 동일한 계약:
        {"url"|"target": str, "pages_scanned": int,
         "features": [{"category_major","category_mid","category_leaf",
                       "implicit_spec","confidence","source_url"|"source_element",
                       "target_ref": {...}}]}
    None 반환 시 Stage 0 생략(입력 파일/스펙만 사용).
    """
    def scan(self, *, config: Any, llm: Any, run_dir: Path,
             progress_cb: ProgressCb, should_stop: StopFn) -> Optional[dict]: ...


@runtime_checkable
class Executor(Protocol):
    """Stage 5 대체 — approved/edited TC를 실행하고 result/actual/exec_confidence를 채운다.

    기존 stage5_execute.execute 와 동일한 반환 계약(tcs 리스트를 수정·반환).
    """
    def execute(self, *, tcs: list[dict], config: Any, run_dir: Path,
                progress_cb: ProgressCb, is_paused: StopFn,
                is_stopped: StopFn) -> list[dict]: ...


@runtime_checkable
class OracleVerifier(Protocol):
    """기대 vs 실제 → Verdict. 대상별 오라클 강도가 다르다(API 강, GUI 약)."""
    def verify(self, expected: str, actual: Any, methods: list[str]) -> Verdict: ...


@runtime_checkable
class TargetLocator(Protocol):
    """V6(셀렉터 안정성)의 일반화 — target_ref의 안정성 점수 [0,1]."""
    def stability(self, target_ref: dict) -> float: ...


@dataclass
class TargetAdapter:
    """대상 유형 1종 = Probe + Executor + Locator(+Oracle) 번들."""
    target_kind: str                          # web | api_rest | api_code | gui
    executor: Executor
    locator: TargetLocator
    probe: Optional[Probe] = None
    oracle: Optional[OracleVerifier] = None
    # leaf → 적용 가능한 negative 카테고리(V10용). None이면 코어 기본 키워드 맵 사용.
    negative_category_map: Optional[Callable[[dict], list[str]]] = None
    # TC → (automation_grade A~D, manual_action_required)
    grade_rules: Optional[Callable[[dict, "TargetAdapter"], tuple[str, str]]] = None
    label: str = ""
