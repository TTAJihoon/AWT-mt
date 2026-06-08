"""실제 공개 API 라이브 테스트 — Swagger Petstore (실 OpenAPI + 실 LLM + 실 HTTP).

공유 서버 예의: **GET 엔드포인트만** 필터링해 시험(쓰기/삭제 제외).
키는 환경변수 OPENAI_API_KEY로만 받는다(파일/커밋 미저장). 모델 OPENAI_MODEL(기본 gpt-5.4-nano).

실행:
  OPENAI_API_KEY=... OPENAI_MODEL=gpt-5.4-nano \
  PYTHONIOENCODING=utf-8 python scripts/demo_live_petstore.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import os
from collections import Counter

import httpx

from app.core.orchestrator import Orchestrator, RunConfig

_SPEC_URL = "https://petstore3.swagger.io/api/v3/openapi.json"
_BASE_URL = "https://petstore3.swagger.io/api/v3"
_HTTP = ("get", "put", "post", "patch", "delete", "head", "options")


def _get_only(spec: dict) -> dict:
    """GET operation만 남긴다(공유 서버에 부작용 없는 안전 시험)."""
    paths = spec.get("paths", {})
    for path in list(paths.keys()):
        item = paths[path]
        for method in list(item.keys()):
            if method.lower() in _HTTP and method.lower() != "get":
                del item[method]
        if not any(m.lower() == "get" for m in item):
            del paths[path]
    return spec


def main() -> None:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print("OPENAI_API_KEY 환경변수가 필요합니다."); return
    model = os.environ.get("OPENAI_MODEL", "gpt-5.4-nano")

    run_dir = Path("data/runs/petstore-live"); run_dir.mkdir(parents=True, exist_ok=True)
    spec = _get_only(httpx.get(_SPEC_URL, timeout=30).json())
    (run_dir / "openapi.json").write_text(json.dumps(spec), encoding="utf-8")
    print(f"Petstore GET 엔드포인트 {len(spec['paths'])}개로 시험 (base={_BASE_URL})")

    config = RunConfig(
        api_key=key, target_url="", run_id="petstore-live",
        target_kind="api_rest",
        target_config={"openapi_path": str(run_dir / "openapi.json"), "base_url": _BASE_URL},
        model_override=model,
        consolidate_features=False, feature_gate=False,
        inferred_threshold=1.0, max_leaves=0, concurrency=2,
    )
    print(f"실 LLM 풀런 — provider=openai model={model}")
    orch = Orchestrator(config, progress_cb=lambda m: print("  ", m))

    fs = orch.run_stage0()
    orch.run_stage1(fs)
    orch.run_stage2()
    orch.run_stage3()
    orch.apply_gate_decisions({tc["tc_id"]: {"status": "approved"} for tc in orch.tcs})
    orch.run_stage5()
    orch.run_stage6()
    out = orch.run_stage7()

    print("\n=== 생성·실행된 TC (실 Petstore) ===")
    for tc in orch.tcs:
        if tc.get("tc_id", "").startswith("TC-FLOW"):
            continue
        print(f"  [{str(tc.get('result')).upper():7}] {tc.get('tc_id')} {tc.get('소분류')} "
              f"| {tc.get('design_technique')}/{tc.get('negative_category') or '-'}")
        print(f"           {tc.get('scenario','')[:75]}")
        print(f"           test_data={tc.get('test_data','-')}  →  {str(tc.get('actual',''))[:70]}")
    print("\n=== 요약 ===")
    print(f"  총 {len(orch.tcs)} | 결과 {dict(Counter(t.get('result') for t in orch.tcs))}"
          f" | 등급 {dict(Counter(t.get('automation_grade') for t in orch.tcs))}")
    print(f"  Excel: {out}  | 보고서: {run_dir / 'report' / 'test_report.md'}")


if __name__ == "__main__":
    main()
