"""전체 파이프라인 풀런 데모 (작업: 통합+풀런).

orchestrator로 Stage 0~7을 api_rest 대상에 대해 한 번에 실행 → 실제 tc_final.xlsx +
report/test_report.md 산출. 외부 LLM 키 없이 MockLLMClient 주입.

실행: PYTHONIOENCODING=utf-8 python scripts/demo_full_pipeline.py
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
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.api.mock_llm_client import MockLLMClient
from app.core.orchestrator import Orchestrator, RunConfig

_OPENAPI = {
    "openapi": "3.0.0", "info": {"title": "demo", "version": "1"},
    "paths": {
        "/items": {
            "get": {"tags": ["items"], "operationId": "list", "responses": {"200": {}}},
            "post": {"tags": ["items"], "operationId": "create",
                     "requestBody": {"content": {"application/json": {"schema": {
                         "type": "object", "required": ["name"],
                         "properties": {"name": {"type": "string"}}}}}},
                     "responses": {"201": {}, "400": {}}},
        },
        "/items/{id}": {"get": {"tags": ["items"], "operationId": "get",
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
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    spec_path = Path("data/runs/demo-full"); spec_path.mkdir(parents=True, exist_ok=True)
    (spec_path / "openapi.json").write_text(json.dumps(_OPENAPI), encoding="utf-8")

    config = RunConfig(
        api_key="mock", target_url="", run_id="demo-full",
        target_kind="api_rest",
        target_config={"openapi_path": str(spec_path / "openapi.json"), "base_url": base},
        consolidate_features=False, feature_gate=False,
        inferred_threshold=1.0, max_leaves=0, concurrency=1,
    )
    orch = Orchestrator(config, progress_cb=lambda m: print("  ", m),
                        llm_client=MockLLMClient(run_id="demo-full"))

    feature_spec = orch.run_stage0()      # api_rest Probe (OpenAPI)
    orch.run_stage1(feature_spec)          # ingest
    orch.run_stage2()                      # TC 설계 (Mock)
    orch.run_stage3()                      # V1~V10
    orch.apply_gate_decisions({tc["tc_id"]: {"status": "approved"} for tc in orch.tcs})
    orch.run_stage5()                      # 실제 HTTP 실행 (+ test_data 보강 시도)
    orch.run_stage6()                      # 실패 분석
    out = orch.run_stage7()                # Excel
    server.shutdown()

    from collections import Counter
    res = Counter(tc.get("result") for tc in orch.tcs)
    grade = Counter(tc.get("automation_grade") for tc in orch.tcs)
    print("\n=== 풀런 결과 ===")
    print(f"  총 TC: {len(orch.tcs)}  | 결과: {dict(res)}  | 등급: {dict(grade)}")
    print(f"  Excel: {out}")
    report = Path("data/runs/demo-full/report/test_report.md")
    if report.exists():
        print(f"  보고서: {report}\n--- 보고서 발췌 ---")
        print("\n".join(report.read_text(encoding="utf-8").splitlines()[:22]))


if __name__ == "__main__":
    main()
