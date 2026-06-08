"""Gemini 3.5 Flash 실행 재개 스크립트 — quota 리셋 후 원클릭 완료.

배경:
    Stage 2에서 gemini-3.5-flash 일일 quota(20 req/day)를 소진해
    F001-F022 (22개) 완료 후 중단된 상태. data/llm_cache/ 에 22개 캐시됨.

이 스크립트는:
    1. run_id='gemini35_run_01'로 기존 run 디렉터리 재사용
    2. Stage 1 재실행 (파일 파싱, API 호출 없음)
    3. Stage 2 재실행 (F001-F022 캐시 히트, F023-F026만 API 호출)
    4. Stage 3 실행 (V1~V10 검증 + TC 보완)

사용법:
    python scripts/resume_gemini_run.py

    # API 키를 환경변수로 덮어쓸 때:
    set GOOGLE_API_KEY=AIzaSy...
    python scripts/resume_gemini_run.py

    # 새 모델로 시도할 때 (다른 run_id 자동 생성):
    python scripts/resume_gemini_run.py --model gemini-2.5-flash --new-run

quota 확인:
    https://aistudio.google.com/quota
    gemini-3.5-flash Free tier: 20 req/day → 매일 자정(UTC) 리셋

캐시 현황:
    data/llm_cache/ — 35개 캐시 파일 (TC_DESIGN × 22 leaf + 기타)
    캐시된 leaf: F001~F022
    미완료 leaf: F023~F026 (4개)
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

# Windows cp949 터미널에서 한글/특수문자 인코딩 오류 방지
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# .env 자동 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.config.settings import load_api_key, get_active_provider
from app.core.orchestrator import Orchestrator, RunConfig

_MANUAL = ROOT / "data/oss/gnuboard5/manual/gnuboard5_spec.md"
_DEFAULT_RUN_ID = "gemini35_run_01"
_DEFAULT_MODEL = "gemini-3.5-flash"


def main() -> None:
    parser = argparse.ArgumentParser(description="Gemini Stage 1~3 재개 실행")
    parser.add_argument(
        "--manual",
        default=str(_MANUAL),
        help=f"매뉴얼 파일 경로 (기본: {_MANUAL.name})",
    )
    parser.add_argument(
        "--model",
        default=_DEFAULT_MODEL,
        help=f"모델 override (기본: {_DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--run-id",
        default=_DEFAULT_RUN_ID,
        help=f"run ID — 기존 run 재사용 (기본: {_DEFAULT_RUN_ID})",
    )
    parser.add_argument(
        "--new-run",
        action="store_true",
        help="새 run ID 생성 (기존 캐시는 그대로 재사용됨)",
    )
    parser.add_argument("--threshold", type=float, default=0.30)
    args = parser.parse_args()

    # API 키 로드: 환경변수 > 암호화 저장소
    api_key = load_api_key("google") or ""
    if not api_key:
        print("❌ Google API 키가 없습니다.")
        print("   방법 1: set GOOGLE_API_KEY=AIzaSy...")
        print("   방법 2: 앱 UI에서 Google API 키 저장")
        print("   방법 3: python -c \"from app.config.settings import save_api_key; save_api_key('AIzaSy...', 'google')\"")
        sys.exit(1)

    manual_path = Path(args.manual)
    if not manual_path.exists():
        print(f"❌ 매뉴얼 파일 없음: {manual_path}")
        sys.exit(1)

    run_id = None if args.new_run else args.run_id

    config = RunConfig(
        api_key=api_key,
        target_url="http://localhost:8080",
        input_files=[str(manual_path)],
        inferred_threshold=args.threshold,
        model_override=args.model,
        run_id=run_id or __import__("uuid").uuid4().hex[:8],
    )
    # run_id 고정 (new_run이 아닌 경우)
    if not args.new_run:
        config.run_id = _DEFAULT_RUN_ID

    print(f"{'='*60}")
    print(f"  AWT Gemini Stage 1~3 재개 실행")
    print(f"  Run ID   : {config.run_id}")
    print(f"  모델     : {config.model_override}")
    print(f"  매뉴얼   : {manual_path.name}")
    print(f"  임계값   : INFERRED ≤ {args.threshold:.0%}")
    print(f"{'='*60}")
    print(f"  [i] 캐시된 leaf (F001~F022)는 API 호출 없이 즉시 로드됩니다.")
    print(f"  [i] gemini-3.5-flash 일일 quota: 20 req/day (UTC 자정 리셋)")
    print(f"{'='*60}")

    orch = Orchestrator(config, progress_cb=_cb)
    t0 = time.time()

    # Stage 1: 파싱 (캐시와 무관, 빠름)
    ingest = orch.run_stage1()
    leaves = ingest["leaves"]
    print(f"\n  → leaf 기능 {len(leaves)}개 추출:")
    for lf in leaves[:5]:
        print(f"     {lf['requirement_id']}  {lf['category_leaf']}")
    if len(leaves) > 5:
        print(f"     ... 외 {len(leaves)-5}개")

    # Stage 2: TC 설계 (캐시 히트 + 미완료 leaf만 API 호출)
    print(f"\n  [Stage 2] TC 설계 — 캐시 히트 leaf는 즉시 로드, 신규 leaf만 API 호출")
    tcs = orch.run_stage2()
    print(f"\n  → TC {len(tcs)}개 생성")

    # Stage 3: 검증
    print(f"\n  [Stage 3] V1~V10 검증")
    tcs = orch.run_stage3()

    elapsed = time.time() - t0
    run_dir = orch.run_dir

    # 결과 요약
    techniques: dict[str, int] = {}
    for tc in tcs:
        t = tc.get("design_technique", "?")
        techniques[t] = techniques.get(t, 0) + 1

    neg_cats: dict[str, int] = {}
    for tc in tcs:
        nc = tc.get("negative_category")
        if nc:
            neg_cats[nc] = neg_cats.get(nc, 0) + 1

    inferred = sum(1 for tc in tcs if str(tc.get("source_quote", "")).startswith("INFERRED"))

    print(f"\n{'='*60}")
    print(f"  ✅ 완료  ({elapsed:.0f}초)")
    print(f"  TC 총계  : {len(tcs)}개")
    print(f"  INFERRED : {inferred}/{len(tcs)} ({inferred/len(tcs):.1%})")
    print(f"\n  기법 분포:")
    for tech, cnt in sorted(techniques.items(), key=lambda x: -x[1]):
        bar = "█" * min(cnt, 40)
        print(f"    {tech:<25} {bar} {cnt}")
    if neg_cats:
        print(f"\n  음성 카테고리 분포:")
        for cat, cnt in sorted(neg_cats.items(), key=lambda x: -x[1]):
            print(f"    {cat:<25} {cnt}")
    print(f"\n  산출물:")
    print(f"    {run_dir / 'tc_raw.json'}")
    print(f"    {run_dir / 'tc_verified.json'}")
    print(f"    {run_dir / 'tc_review.xlsx'}  ← Reviewer Gate용")
    print(f"{'='*60}\n")


def _cb(msg: str) -> None:
    print(f"  {msg}")


if __name__ == "__main__":
    main()
