"""Stage 5 — Playwright TC 자동 실행 (D40 고도화).

변경 이력:
  D39 — 기본 구현: page.inner_text("body") 키워드 매칭
  D40 — 고도화: GnuboardTestEngine 통합 (URL 라우팅 + 픽스처 + 액션 엔진)
"""
from __future__ import annotations
import time
from typing import Callable

from playwright.sync_api import sync_playwright, Page, expect
from app.validation.v6_selector_stability import annotate as v6_annotate, format_report as v6_format


def execute(
    tcs: list[dict],
    base_url: str,
    auth_sequence: list[dict] | None = None,
    progress_cb: Callable[[str], None] | None = None,
    headless: bool = True,
    slow_mo_ms: int = 0,
    is_paused: Callable[[], bool] | None = None,
    is_stopped: Callable[[], bool] | None = None,
) -> list[dict]:
    """approved/edited TC를 Playwright로 실행. result/actual/exec_confidence 채움.

    Args:
        headless:   False면 별도 Chromium 창이 떠 사용자가 동작을 볼 수 있음.
        slow_mo_ms: 액션 사이 인공 지연 (ms). 헤드풀 모드에서 동작을 천천히 보기 위함.
        is_paused:  매 TC 시작 전 호출, True면 False가 될 때까지 대기 (협력적 일시정지).
        is_stopped: 매 TC 시작 전 호출, True면 즉시 종료 (협력적 중단).
    """
    def _cb(msg: str):
        if progress_cb:
            progress_cb(msg)

    def _wait_if_paused() -> bool:
        """일시정지/중단 신호를 협력적으로 처리. 중단되면 True 반환."""
        if is_stopped and is_stopped():
            return True
        if is_paused and is_paused():
            import time as _t
            _cb("⏸  사용자가 일시정지함 — 재개를 기다립니다…")
            while is_paused():
                if is_stopped and is_stopped():
                    return True
                _t.sleep(0.3)
            _cb("▶  실행 재개")
        return False

    runnable = [tc for tc in tcs if tc.get("review_status") in ("approved", "edited")]
    mode_label = "헤드풀 (브라우저 표시)" if not headless else "헤드리스"
    _cb(
        f"Stage 5: {len(runnable)}개 TC 자동 실행 시작 (D40 고도화 엔진, {mode_label})"
    )

    # gnuboard5 전용 엔진 사용 여부 판단
    # auth_sequence에서 admin_id/admin_pw 추출 시도
    admin_id, admin_pw = _extract_admin_creds(auth_sequence)

    with sync_playwright() as p:
        launch_kwargs: dict = {"headless": headless}
        if slow_mo_ms > 0:
            launch_kwargs["slow_mo"] = slow_mo_ms
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context()
        page = context.new_page()

        page.goto(base_url, wait_until="networkidle", timeout=30000)

        # 초기 로그인 (auth_sequence)
        if auth_sequence:
            _run_auth(page, auth_sequence)

        # gnuboard 엔진 감지 — tcs에 소분류 필드가 있으면 고도화 엔진 사용
        use_gnuboard = any(tc.get("소분류") for tc in runnable[:3])

        if use_gnuboard:
            from app.core.stage5_gnuboard import (
                GnuboardFixtures, setup_fixtures, execute_tc as gb_execute_tc,
            )
            fixtures = GnuboardFixtures(admin_id=admin_id, admin_pw=admin_pw)
            # 초기 상태: auth_sequence로 이미 로그인됨
            if admin_id:
                fixtures.logged_in_as = "admin"

            _cb("  [D40] GnuBoard5 엔진 초기화 - 픽스처 설정 시작")
            try:
                setup_fixtures(page, base_url, fixtures,
                               admin_id=admin_id, admin_pw=admin_pw, cb=_cb)
            except Exception as e:
                _cb(f"  [D40] 픽스처 설정 실패 (무시): {e}")

            _cb(f"  [D40] TC 실행 시작")
            for i, tc in enumerate(runnable, 1):
                # 일시정지/중단 협력적 체크 (매 TC 시작 전)
                if _wait_if_paused():
                    _cb(f"⏹  사용자가 중단 요청 — {i-1}/{len(runnable)}개 실행 후 종료")
                    break
                _cb(f"  실행 ({i}/{len(runnable)}): {tc['tc_id']} [{tc.get('소분류','')}]")
                tc["exec_mode"] = "D40_scenario"
                gb_execute_tc(page, tc, base_url, fixtures, cb=_cb)

        else:
            # fallback: 기존 shallow 실행
            _cb("  [D39] 기본 엔진으로 실행 (소분류 필드 없음)")
            for i, tc in enumerate(runnable, 1):
                if _wait_if_paused():
                    _cb(f"⏹  사용자가 중단 요청 — {i-1}/{len(runnable)}개 실행 후 종료")
                    break
                _cb(f"  실행 중 ({i}/{len(runnable)}): {tc['tc_id']}")
                tc["exec_mode"] = "D39_keyword_match"
                _run_tc(page, tc, base_url)

        browser.close()

    # 실행 제외 TC → not_executed
    not_run = [tc for tc in tcs if tc.get("review_status") not in ("approved", "edited")]
    for tc in not_run:
        tc["result"] = "not_executed"

    # V6: 선택자 안정성 점수 + 실패 분류 보정
    tcs, v6_report = v6_annotate(tcs, overwrite_exec_confidence=True)
    _cb(v6_format(v6_report))

    _cb("Stage 5 완료")
    return tcs


def _extract_admin_creds(auth_sequence: list[dict] | None) -> tuple[str, str]:
    """auth_sequence에서 admin_id, admin_pw 추출."""
    if not auth_sequence:
        return "admin", "Gnuboard5!"
    admin_id, admin_pw = "admin", "Gnuboard5!"
    for step in auth_sequence:
        if step.get("action") == "fill":
            sel = step.get("selector", "")
            val = step.get("value", "")
            if "id" in sel:
                admin_id = val
            elif "pw" in sel or "password" in sel:
                admin_pw = val
    return admin_id, admin_pw


def _run_auth(page: Page, auth_sequence: list[dict]) -> None:
    for step in auth_sequence:
        action = step.get("action")
        if action == "goto":
            page.goto(step["url"], wait_until="networkidle")
        elif action == "fill":
            selector = step["selector"]
            value = step.get("value", "")
            # submit/button 타입은 fill 불가 → click으로 자동 전환
            el = page.query_selector(selector)
            el_type = ""
            if el:
                try:
                    el_type = (el.get_attribute("type") or "").lower()
                except Exception:
                    pass
            if el_type in ("submit", "button", "reset") or not value:
                page.click(selector)
                page.wait_for_load_state("networkidle", timeout=10000)
            else:
                page.fill(selector, value)
        elif action == "click":
            page.click(step["selector"])
            page.wait_for_load_state("networkidle", timeout=10000)


# ─── D39 fallback 구현 (소분류 없는 TC용) ──────────────────────────────────

def _run_tc(page: Page, tc: dict, base_url: str) -> None:
    start = time.time()
    try:
        _apply_precondition(page, tc.get("precondition", ""), base_url)
        expected = tc.get("expected", "")
        try:
            actual_text = page.inner_text("body") or ""
        except Exception:
            actual_text = page.content()
        actual_snippet = actual_text[:500]

        if expected and any(kw in actual_text for kw in _key_phrases(expected)):
            tc["result"] = "pass"
            tc["actual"] = f"기대 패턴 확인: {expected[:100]}"
        else:
            tc["result"] = "fail"
            tc["actual"] = f"페이지 텍스트 일부: {actual_snippet}"

        elapsed = time.time() - start
        tc["exec_confidence"] = min(1.0, round(0.9 - elapsed * 0.01, 2))

    except Exception as e:
        tc["result"] = "blocked"
        tc["actual"] = f"실행 오류: {str(e)[:200]}"
        tc["exec_confidence"] = 0.1


def _apply_precondition(page: Page, precondition: str, base_url: str) -> None:
    lower = precondition.lower()
    if "로그인" in lower and "비로그인" not in lower:
        if "로그아웃" not in page.content():
            page.goto(base_url, wait_until="networkidle", timeout=15000)
    elif "비로그인" in lower:
        page.goto(base_url, wait_until="networkidle", timeout=15000)
    else:
        page.goto(base_url, wait_until="networkidle", timeout=15000)


def _key_phrases(expected: str) -> list[str]:
    """기대 출력에서 검증 키워드 추출 (D39 fallback용)."""
    import re
    quoted = re.findall(r"[`'\"](.+?)[`'\"]", expected)
    if quoted:
        return quoted
    words = [w for w in expected.split() if len(w) > 3]
    return words[:5] if words else [expected[:30]]
