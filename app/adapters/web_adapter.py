"""web 어댑터 (D60) — 기존 Stage 0/5를 어댑터로 래핑(동작 변화 0, 회귀 방지).

추상화가 기존 웹 파이프라인을 그대로 담을 수 있음을 증명한다. playwright는
scan/execute 호출 시점에만 lazy import (모듈 로드 비용 회피).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.adapters.base import ProgressCb, StopFn, TargetAdapter
from app.adapters.registry import register


class _WebProbe:
    def scan(self, *, config: Any, llm: Any, run_dir: Path,
             progress_cb: ProgressCb, should_stop: StopFn):
        from app.core import stage0_dom_scan
        return stage0_dom_scan.scan(
            url=config.target_url,
            llm_client=llm,
            run_dir=run_dir,
            auth_sequence=config.auth_sequence or None,
            max_pages=config.max_pages,
            progress_cb=progress_cb,
            selected_urls=config.selected_urls,
            cached_features=config.cached_features,
            should_stop=should_stop,
            dedup_global_components=config.dedup_global_components,
            global_ratio=config.global_ratio,
            collapse_nav_links=config.collapse_nav_links,
            nav_link_keep=config.nav_link_keep,
        )


class _WebExecutor:
    def execute(self, *, tcs: list[dict], config: Any, run_dir: Path,
                progress_cb: ProgressCb, is_paused: StopFn, is_stopped: StopFn):
        from app.core import stage5_execute
        return stage5_execute.execute(
            tcs=tcs,
            base_url=config.target_url,
            auth_sequence=config.auth_sequence or None,
            progress_cb=progress_cb,
            headless=config.headless_exec,
            slow_mo_ms=config.slow_mo_ms,
            is_paused=is_paused,
            is_stopped=is_stopped,
        )


class _WebLocator:
    def stability(self, target_ref: dict) -> float:
        # 웹 셀렉터 안정성은 stage5의 V6가 exec 후 정밀 계산한다.
        # 여기선 보조 기본값만 제공(이미 V6가 채웠으면 grading이 덮어쓰지 않음).
        return float(target_ref.get("score", 0.62))


def _web_grade(tc: dict, adapter: TargetAdapter) -> tuple[str, str]:
    # 웹: UI/로그 검증 가능하면 A. exec_confidence가 낮으면 B로 강등.
    ec = tc.get("exec_confidence")
    if isinstance(ec, (int, float)) and ec < 0.5:
        return "B", ""
    return "A", ""


def _factory() -> TargetAdapter:
    return TargetAdapter(
        target_kind="web",
        probe=_WebProbe(),
        executor=_WebExecutor(),
        locator=_WebLocator(),
        grade_rules=_web_grade,
        label="웹 (DOM/Playwright)",
    )


register("web", _factory, label="웹 (DOM/Playwright)")
