"""Stage 1~3 독립 실행 스크립트 — Docker/PostgreSQL 없이 TC 설계 테스트.

사용법:
    # 환경변수로 API key 전달
    set ANTHROPIC_API_KEY=sk-ant-...
    python scripts/run_stage123.py

    # 또는 .env 파일 사용 (python-dotenv 자동 로드)
    python scripts/run_stage123.py

옵션:
    --manual  <path>   입력 매뉴얼 파일 (기본: data/oss/gnuboard5/manual/gnuboard5_spec.md)
    --out-dir <path>   결과 저장 디렉터리 (기본: data/runs/<run_id>)
    --threshold <float> INFERRED 임계값 (기본: 0.30)
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

# .env 자동 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 프로젝트 루트를 경로에 추가
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.core.orchestrator import Orchestrator, RunConfig
from app.tools.excel_builder import build_review


def main() -> None:
    parser = argparse.ArgumentParser(description="AWT Stage 1~3 빠른 실행")
    parser.add_argument(
        "--manual",
        default=str(ROOT / "data/oss/gnuboard5/manual/gnuboard5_spec.md"),
        help="입력 매뉴얼 파일 경로",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8080",
        help="대상 URL (Stage 5용, 지금은 메타데이터만 사용)",
    )
    parser.add_argument("--threshold", type=float, default=0.30)
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY 환경변수가 없습니다.")
        print("   set ANTHROPIC_API_KEY=sk-ant-...  또는 .env 파일에 추가하세요.")
        sys.exit(1)

    manual_path = Path(args.manual)
    if not manual_path.exists():
        print(f"❌ 매뉴얼 파일을 찾을 수 없습니다: {manual_path}")
        sys.exit(1)

    config = RunConfig(
        api_key=api_key,
        target_url=args.url,
        input_files=[str(manual_path)],
        inferred_threshold=args.threshold,
    )

    print(f"{'='*60}")
    print(f"  AWT Stage 1~3 실행")
    print(f"  Run ID   : {config.run_id}")
    print(f"  매뉴얼   : {manual_path.name}")
    print(f"  임계값   : INFERRED ≤ {args.threshold:.0%}")
    print(f"{'='*60}")

    orch = Orchestrator(config, progress_cb=_cb)

    t0 = time.time()

    # Stage 1: 파일 파싱
    ingest = orch.run_stage1()
    leaves = ingest["leaves"]
    print(f"\n  → leaf 기능 {len(leaves)}개 추출:")
    for lf in leaves[:10]:
        print(f"     {lf['requirement_id']}  {lf['leaf']}")
    if len(leaves) > 10:
        print(f"     ... 외 {len(leaves)-10}개")

    # Stage 2: TC 설계
    tcs = orch.run_stage2()
    print(f"\n  → TC {len(tcs)}개 생성")

    # Stage 3: 검증
    tcs = orch.run_stage3()

    elapsed = time.time() - t0
    run_dir = orch.run_dir

    # 결과 요약
    statuses = {}
    for tc in tcs:
        s = tc.get("review_status", "pending")
        statuses[s] = statuses.get(s, 0) + 1

    techniques = {}
    for tc in tcs:
        t = tc.get("design_technique", "?")
        techniques[t] = techniques.get(t, 0) + 1

    inferred = sum(1 for tc in tcs if str(tc.get("source_quote", "")).startswith("INFERRED"))

    print(f"\n{'='*60}")
    print(f"  완료  ({elapsed:.1f}초)")
    print(f"  TC 총계  : {len(tcs)}개")
    print(f"  INFERRED : {inferred}/{len(tcs)} ({inferred/len(tcs):.1%})")
    print(f"  기법 분포:")
    for tech, cnt in sorted(techniques.items(), key=lambda x: -x[1]):
        bar = "█" * cnt
        print(f"    {tech:<20} {bar} {cnt}")
    print(f"{'='*60}")
    print(f"\n  산출물:")
    print(f"    {run_dir / 'tc_raw.json'}")
    print(f"    {run_dir / 'tc_verified.json'}")
    print(f"    {run_dir / 'tc_review.xlsx'}  ← Reviewer Gate용")
    print()


def _cb(msg: str) -> None:
    print(f"  {msg}")


if __name__ == "__main__":
    main()
