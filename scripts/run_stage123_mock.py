"""Stage 1~3 Mock 실행 — API key 없이 TC 설계 테스트.

사용법:
    python scripts/run_stage123_mock.py
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.api.mock_llm_client import MockLLMClient
from app.core.orchestrator import Orchestrator, RunConfig
from app.tools.excel_builder import build_review


def main() -> None:
    manual = ROOT / "data/oss/gnuboard5/manual/gnuboard5_spec.md"
    if not manual.exists():
        print(f"❌ 매뉴얼 파일 없음: {manual}")
        sys.exit(1)

    config = RunConfig(
        api_key="mock",
        target_url="http://localhost:8080",
        input_files=[str(manual)],
        inferred_threshold=0.30,
    )

    print(f"\n{'='*60}")
    print(f"  AWT Stage 1~3  [MOCK MODE - API 호출 없음]")
    print(f"  Run ID  : {config.run_id}")
    print(f"  매뉴얼  : {manual.name}")
    print(f"{'='*60}\n")

    # Mock 클라이언트 주입
    mock = MockLLMClient(run_id=config.run_id)
    orch = Orchestrator(config, progress_cb=lambda m: print(f"  {m}"))
    orch.llm = mock                       # LLM 클라이언트 교체

    t0 = time.time()

    # Stage 1
    ingest = orch.run_stage1()
    leaves = ingest["leaves"]
    print(f"\n  ── leaf 목록 ({len(leaves)}개) ──")
    for lf in leaves:
        print(f"    {lf['requirement_id']:5s}  {lf['category_major']} > "
              f"{lf['category_mid']} > {lf['category_leaf']}")

    # Stage 2
    tcs = orch.run_stage2()

    # Stage 3
    tcs = orch.run_stage3()

    elapsed = time.time() - t0
    run_dir = orch.run_dir

    # ── 결과 요약 ──────────────────────────────────────────────────────
    techniques: dict[str, int] = {}
    for tc in tcs:
        t = tc.get("design_technique", "?")
        techniques[t] = techniques.get(t, 0) + 1

    inferred = [tc for tc in tcs if str(tc.get("source_quote", "")).startswith("INFERRED")]
    statuses: dict[str, int] = {}
    for tc in tcs:
        s = tc.get("review_status", "pending")
        statuses[s] = statuses.get(s, 0) + 1

    print(f"\n{'='*60}")
    print(f"  완료  ({elapsed:.1f}초) | Mock LLM 호출 {mock._call_count}회")
    print(f"  TC 총계     : {len(tcs)}개")
    print(f"  INFERRED    : {len(inferred)}/{len(tcs)} ({len(inferred)/len(tcs):.1%})")
    print(f"\n  기법 분포:")
    for tech, cnt in sorted(techniques.items(), key=lambda x: -x[1]):
        bar = "█" * cnt
        pct = cnt / len(tcs) * 100
        print(f"    {tech:<22} {bar:<30} {cnt:3d} ({pct:.0f}%)")
    print(f"\n  검토 상태:")
    for s, cnt in statuses.items():
        print(f"    {s:<12} {cnt}개")
    print(f"\n  산출물 위치: {run_dir}")
    print(f"    tc_raw.json      — Stage 2 원본")
    print(f"    tc_verified.json — Stage 3 검증 후")
    print(f"    tc_review.xlsx   — Reviewer Gate용 Excel")
    print(f"{'='*60}\n")

    # TC 샘플 출력 (처음 5개)
    print("  ── TC 샘플 (처음 5개) ──")
    for tc in tcs[:5]:
        print(f"\n  [{tc['tc_id']}] {tc.get('대분류')} > {tc.get('소분류')}")
        print(f"  시나리오  : {tc.get('scenario')}")
        print(f"  사전조건  : {tc.get('precondition','')[:70]}")
        print(f"  기대결과  : {tc.get('expected','')[:70]}")
        print(f"  기법      : {tc.get('design_technique')}  신뢰도: {tc.get('gen_confidence')}")


if __name__ == "__main__":
    main()
