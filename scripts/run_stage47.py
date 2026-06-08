"""Stage 4~7 실행 스크립트 — Stage 3 완료 이후 이어서 실행.

Stage 3 산출물(tc_verified.json)을 로드한 뒤
  Stage 4: Reviewer Gate (CLI 모드 = 전체 자동 승인)
  Stage 5: Playwright 자동 실행 (그누보드5 Docker 필요)
  Stage 6: 실패 원인 LLM 분석
  Stage 7: Excel 최종 산출

사전 요건:
  1. 그누보드5 Docker 컨테이너 실행 중
       docker compose -f data/oss/gnuboard5/docker-compose.yml up -d
  2. 그누보드5 웹 설치 완료 (http://localhost:8080/install)
  3. Google API 키 저장됨 (~/.awt/settings.enc)

사용법:
    # 가장 최근 run_id 자동 감지
    python scripts/run_stage47.py --url http://localhost:8080

    # run_id 명시
    python scripts/run_stage47.py --run-id c0995b8b --url http://localhost:8080

    # 관리자 계정으로 로그인하여 Stage 5 실행
    python scripts/run_stage47.py --url http://localhost:8080 --auth-id admin --auth-pw <비밀번호>

    # Stage 5 스킵 (Playwright 없이 Stage 6~7만 실행)
    python scripts/run_stage47.py --url http://localhost:8080 --skip-stage5
"""
from __future__ import annotations
import argparse
import os
import sys
import time
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.config.settings import load_api_key
from app.core.orchestrator import Orchestrator, RunConfig, RUNS_DIR


def _latest_run_with_stage3() -> str | None:
    """tc_verified.json이 있는 가장 최근 run_id 반환."""
    runs = sorted(RUNS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for r in runs:
        if (r / "tc_verified.json").exists():
            return r.name
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="AWT Stage 4~7 실행")
    parser.add_argument("--run-id", default="", help="재개할 run ID (없으면 최근 run 자동 감지)")
    parser.add_argument("--url", default="http://localhost:8080", help="대상 URL")
    parser.add_argument("--auth-id", default="admin", help="로그인 아이디")
    parser.add_argument("--auth-pw", default="", help="로그인 비밀번호")
    # 그누보드5 로그인 폼 셀렉터 (실제 HTML: id="login_id", id="login_pw")
    parser.add_argument("--auth-id-selector",     default="#login_id")
    parser.add_argument("--auth-pw-selector",     default="#login_pw")
    parser.add_argument("--auth-submit-selector", default=".btn_submit")
    parser.add_argument("--skip-stage5", action="store_true", help="Playwright 실행 스킵")
    args = parser.parse_args()

    # API 키: Google 우선, 없으면 Anthropic (Stage 6 LLM 분석용)
    api_key = load_api_key("google") or load_api_key("anthropic") or ""
    if not api_key:
        print("ERROR: Google 또는 Anthropic API 키가 없습니다.")
        print("  set GOOGLE_API_KEY=AIzaSy...  또는  set ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    # run_id 결정
    run_id = args.run_id or _latest_run_with_stage3()
    if not run_id:
        print("ERROR: tc_verified.json이 있는 run이 없습니다. 먼저 Stage 1~3을 실행하세요.")
        sys.exit(1)

    verified_path = RUNS_DIR / run_id / "tc_verified.json"
    if not verified_path.exists():
        print(f"ERROR: {verified_path} 를 찾을 수 없습니다.")
        sys.exit(1)

    # 인증 시퀀스
    auth_sequence = []
    if args.auth_id and args.auth_pw:
        login_url = args.url.rstrip("/") + "/bbs/login.php"
        auth_sequence = [
            {"action": "goto",  "url": login_url},
            {"action": "fill",  "selector": args.auth_id_selector, "value": args.auth_id},
            {"action": "fill",  "selector": args.auth_pw_selector, "value": args.auth_pw},
            {"action": "click", "selector": args.auth_submit_selector},
        ]

    # Stage 6 LLM 분석용 model_override (Google API 사용 시)
    google_key = load_api_key("google")
    model_override = "gemini-3.1-flash-lite" if google_key else None

    config = RunConfig(
        api_key=api_key,
        target_url=args.url,
        auth_sequence=auth_sequence,
        run_id=run_id,
        model_override=model_override,
    )

    print(f"{'='*60}")
    print(f"  AWT Stage 4~7 실행")
    print(f"  Run ID  : {run_id}")
    print(f"  URL     : {args.url}")
    print(f"  인증    : {'있음 (' + args.auth_id + ')' if auth_sequence else '없음'}")
    print(f"  Stage 5 : {'SKIP' if args.skip_stage5 else '실행'}")
    print(f"{'='*60}")

    orch = Orchestrator(config, progress_cb=lambda m: print(f"  {m}"))

    # tc_verified.json 로드
    ok = orch.load_from_stage3(run_id)
    if not ok:
        print(f"ERROR: {verified_path} 로드 실패")
        sys.exit(1)

    print(f"  tc_verified.json 로드 완료 — TC {len(orch.tcs)}개")

    t0 = time.time()

    # Stage 4: 전체 자동 승인
    print(f"\n  [Stage 4] {len(orch.tcs)}개 TC 전체 자동 승인")
    decisions = {
        tc["tc_id"]: {
            "status": "approved",
            "note": "run_stage47 auto-approved",
            "reviewer_id": "cli",
        }
        for tc in orch.tcs
    }
    orch.apply_gate_decisions(decisions)

    # Stage 5: Playwright 자동 실행
    if args.skip_stage5:
        print(f"\n  [Stage 5] SKIP (--skip-stage5 지정)")
    else:
        print(f"\n  [Stage 5] Playwright 자동 실행 — {args.url}")
        try:
            orch.run_stage5()
        except Exception as e:
            print(f"\n  WARNING: Stage 5 오류 (결과는 not_executed로 저장): {e}")

    # Stage 6: 실패 원인 분석
    print(f"\n  [Stage 6] 실패 원인 LLM 분석")
    orch.run_stage6()

    # Stage 6B: real_defect TC → 결함 카탈로그 자동 피드백
    print(f"\n  [Stage 6B] 결함 카탈로그 피드백")
    new_defects = orch.run_stage6b()
    if new_defects:
        print(f"    신규 결함 {len(new_defects)}건 카탈로그 추가")
        for d in new_defects:
            print(f"      {d['defectId']}: {d['title'][:50]}")

    # Stage 7: Excel 최종 산출
    print(f"\n  [Stage 7] Excel 최종 산출")
    out = orch.run_stage7()

    elapsed = time.time() - t0
    passed  = sum(1 for tc in orch.tcs if tc.get("result") == "pass")
    failed  = sum(1 for tc in orch.tcs if tc.get("result") == "fail")
    blocked = sum(1 for tc in orch.tcs if tc.get("result") == "blocked")
    not_exe = sum(1 for tc in orch.tcs if tc.get("result") == "not_executed")

    print(f"\n{'='*60}")
    print(f"  DONE  ({elapsed:.0f}s)")
    print(f"  TC {len(orch.tcs)}개 결과:")
    print(f"    PASS        : {passed}")
    print(f"    FAIL        : {failed}")
    print(f"    BLOCKED     : {blocked}")
    print(f"    NOT_EXECUTED: {not_exe}")
    print(f"  산출물: {out}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
