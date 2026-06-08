"""Stage 0~7 전체 파이프라인 CLI 실행 (GUI 없이).

사용법:
    python scripts/run_full_pipeline.py \\
        --url http://localhost:8080 \\
        --manual data/oss/gnuboard5/manual/gnuboard5_spec.md \\
        --auth-id admin --auth-pw gnuboard비밀번호

    # Stage 0 스킵 (매뉴얼만 사용):
    python scripts/run_full_pipeline.py \\
        --url http://localhost:8080 \\
        --manual data/oss/gnuboard5/manual/gnuboard5_spec.md \\
        --skip-stage0

리뷰어 Gate는 CLI 모드에서 전체 자동 승인(approved)으로 처리.
"""
from __future__ import annotations
import argparse
import os
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.core.orchestrator import Orchestrator, RunConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="AWT 전체 파이프라인 CLI")
    parser.add_argument("--url", required=True, help="대상 웹 URL")
    parser.add_argument("--manual", default="", help="매뉴얼 파일 경로")
    parser.add_argument("--auth-id", default="", help="로그인 아이디")
    parser.add_argument("--auth-pw", default="", help="로그인 비밀번호")
    parser.add_argument("--auth-id-selector", default="#mb_id")
    parser.add_argument("--auth-pw-selector", default="#mb_password")
    parser.add_argument("--auth-submit-selector", default=".btn_submit")
    parser.add_argument("--skip-stage0", action="store_true")
    parser.add_argument("--threshold", type=float, default=0.30)
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY 환경변수가 없습니다.")
        sys.exit(1)

    # 인증 시퀀스 조립
    auth_sequence = []
    if args.auth_id and args.auth_pw:
        login_url = args.url.rstrip("/") + "/bbs/login.php"
        auth_sequence = [
            {"action": "goto", "url": login_url},
            {"action": "fill", "selector": args.auth_id_selector, "value": args.auth_id},
            {"action": "fill", "selector": args.auth_pw_selector, "value": args.auth_pw},
            {"action": "click", "selector": args.auth_submit_selector},
        ]

    input_files = [args.manual] if args.manual and Path(args.manual).exists() else []

    config = RunConfig(
        api_key=api_key,
        target_url=args.url,
        input_files=input_files,
        auth_sequence=auth_sequence,
        inferred_threshold=args.threshold,
    )

    print(f"\n{'='*60}")
    print(f"  AWT 전체 파이프라인 CLI")
    print(f"  Run ID : {config.run_id}")
    print(f"  URL    : {args.url}")
    print(f"  매뉴얼 : {args.manual or '없음 (Stage 0 결과 사용)'}")
    print(f"  인증   : {'있음 (' + args.auth_id + ')' if auth_sequence else '없음'}")
    print(f"{'='*60}\n")

    orch = Orchestrator(config, progress_cb=lambda m: print(f"  {m}"))
    t0 = time.time()

    try:
        # Stage 0
        feature_spec = None
        if not args.skip_stage0:
            feature_spec = orch.run_stage0()

        # Stage 1~3
        orch.run_stage1(feature_spec)
        orch.run_stage2()
        tcs = orch.run_stage3()

        # Stage 4: CLI 모드 전체 자동 승인
        print(f"\n  [Stage 4] CLI 모드 — {len(tcs)}개 TC 전체 자동 승인")
        decisions = {
            tc["tc_id"]: {"status": "approved", "note": "CLI auto-approved", "reviewer_id": "cli"}
            for tc in tcs
        }
        orch.apply_gate_decisions(decisions)

        # Stage 5~7
        orch.run_stage5()
        orch.run_stage6()
        out = orch.run_stage7()

        elapsed = time.time() - t0
        passed = sum(1 for tc in orch.tcs if tc.get("result") == "pass")
        failed = sum(1 for tc in orch.tcs if tc.get("result") == "fail")
        blocked = sum(1 for tc in orch.tcs if tc.get("result") == "blocked")

        print(f"\n{'='*60}")
        print(f"  ✅ 완료  ({elapsed:.1f}초)")
        print(f"  결과: PASS {passed} / FAIL {failed} / BLOCKED {blocked}")
        print(f"  산출물: {out}")
        print(f"{'='*60}\n")

    except KeyboardInterrupt:
        print("\n  ⚠ 중단됨")
    except Exception as e:
        print(f"\n  ❌ 오류: {e}")
        raise


if __name__ == "__main__":
    main()
