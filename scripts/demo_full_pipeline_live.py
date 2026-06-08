"""실 LLM 풀런 데모 — OpenAI 실제 호출로 Stage 0~7 (api_rest).

키는 환경변수 OPENAI_API_KEY로만 받는다(파일/커밋에 저장하지 않음).
모델은 OPENAI_MODEL(기본 gpt-5.4-nano).

실행:
  OPENAI_API_KEY=... OPENAI_MODEL=gpt-5.4-nano \
  PYTHONIOENCODING=utf-8 python scripts/demo_full_pipeline_live.py
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
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.core.orchestrator import Orchestrator, RunConfig

_OPENAPI = {
    "openapi": "3.0.0", "info": {"title": "demo", "version": "1"},
    "paths": {
        "/items": {
            "get": {"tags": ["items"], "operationId": "list", "summary": "아이템 목록 조회",
                    "responses": {"200": {}}},
            "post": {"tags": ["items"], "operationId": "create", "summary": "아이템 생성",
                     "requestBody": {"content": {"application/json": {"schema": {
                         "type": "object", "required": ["name"],
                         "properties": {"name": {"type": "string"}}}}}},
                     "responses": {"201": {}, "400": {}}},
        },
        "/items/{id}": {"get": {"tags": ["items"], "operationId": "get",
                                "summary": "아이템 단건 조회",
                                "parameters": [{"name": "id", "in": "path", "required": True,
                                                "schema": {"type": "integer"}}],
                                "responses": {"200": {}, "404": {}}}},
    },
}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body=b"{}"):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/items":
            self._send(200, b'{"items": []}')
        elif self.path.startswith("/items/"):
            self._send(200, b'{"id": 1}')
        else:
            self._send(404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(n) or b"{}") if n else {}
        except Exception:
            data = {}
        self._send(400 if "name" not in data else 201,
                   b'{"error":"name required"}' if "name" not in data else b'{"id":1}')


def main() -> None:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print("OPENAI_API_KEY 환경변수가 필요합니다."); return
    model = os.environ.get("OPENAI_MODEL", "gpt-5.4-nano")

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    run_dir = Path("data/runs/demo-live"); run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "openapi.json").write_text(json.dumps(_OPENAPI), encoding="utf-8")

    config = RunConfig(
        api_key=key, target_url="", run_id="demo-live",
        target_kind="api_rest",
        target_config={"openapi_path": str(run_dir / "openapi.json"), "base_url": base},
        model_override=model,
        consolidate_features=False, feature_gate=False,
        inferred_threshold=1.0, max_leaves=0, concurrency=2,
    )
    print(f"실 LLM 풀런 — provider=openai model={model}")
    orch = Orchestrator(config, progress_cb=lambda m: print("  ", m))

    feature_spec = orch.run_stage0()
    orch.run_stage1(feature_spec)
    orch.run_stage2()
    orch.run_stage3()
    orch.apply_gate_decisions({tc["tc_id"]: {"status": "approved"} for tc in orch.tcs})
    orch.run_stage5()
    orch.run_stage6()
    out = orch.run_stage7()
    server.shutdown()

    print("\n=== 생성된 TC (실 LLM) ===")
    for tc in orch.tcs:
        print(f"  [{str(tc.get('result')).upper():5}] {tc.get('tc_id')} {tc.get('소분류')} "
              f"| {tc.get('design_technique')}/{tc.get('negative_category') or '-'} "
              f"| test_data={tc.get('test_data', '-')}")
        print(f"         시나리오: {tc.get('scenario','')[:70]}")
    print("\n=== 요약 ===")
    print(f"  총 {len(orch.tcs)} | 결과 {dict(Counter(t.get('result') for t in orch.tcs))}"
          f" | 등급 {dict(Counter(t.get('automation_grade') for t in orch.tcs))}")
    print(f"  Excel: {out}")


if __name__ == "__main__":
    main()
