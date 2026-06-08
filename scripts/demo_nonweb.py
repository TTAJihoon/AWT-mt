"""비웹 어댑터 end-to-end 데모 (LLM/인증 불필요).

실행: python scripts/demo_nonweb.py
  1) api_code/python — 실제 임시 라이브러리를 리플렉션→호출
  2) api_rest        — 로컬에 실제 HTTP 서버를 띄워 OpenAPI 기반 실행
  3) report_summary  — 자동화등급/결과 보고서(md) 산출

Stage 2(LLM TC 설계)는 손으로 작성한 TC로 모사한다. 나머지(Probe/Executor/Oracle/
등급/보고서)는 전부 실제 어댑터 코드가 동작한다.
"""
from __future__ import annotations

import sys
try:  # Windows 콘솔(cp949)에서도 한글/기호 출력
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

from app.adapters import get_adapter
from app.adapters.grading import annotate_grades
from app.adapters.report_summary import build_report_md


def _cb(msg: str) -> None:
    print("   ", msg)


def _tc(tc_id, leaf, tech, expected="", negcat=""):
    return {"tc_id": tc_id, "소분류": leaf, "design_technique": tech,
            "negative_category": negcat, "expected": expected,
            "review_status": "approved"}


# ─────────────────────────────────────────────────────────────────────────────
# 1) api_code / python
# ─────────────────────────────────────────────────────────────────────────────
_SAMPLE_LIB = '''
def add(a: int, b: int) -> int:
    """두 정수의 합."""
    return a + b

def divide(a: int, b: int) -> float:
    """a를 b로 나눈다. b=0이면 ZeroDivisionError."""
    return a / b

def validate_email(email: str) -> bool:
    """간단 이메일 검증. 형식 위반 시 ValueError."""
    if "@" not in email:
        raise ValueError("invalid email")
    return True
'''


def demo_api_code(tmp: Path) -> list[dict]:
    print("\n=== [1] api_code / python ===")
    lib = tmp / "sample_lib.py"
    lib.write_text(_SAMPLE_LIB, encoding="utf-8")
    cfg = SimpleNamespace(target_config={"lang": "python", "module_path": str(lib)})
    adapter = get_adapter("api_code")

    spec = adapter.probe.scan(config=cfg, llm=None, run_dir=tmp,
                              progress_cb=_cb, should_stop=lambda: False)
    print("  [Probe] 심볼(leaf):", [f["category_leaf"] for f in spec["features"]])

    tcs = [
        _tc("TC-ADD-001", "add", "happy_path"),
        _tc("TC-DIV-001", "divide", "happy_path"),
        _tc("TC-EML-001", "validate_email", "happy_path"),
        _tc("TC-EML-002", "validate_email", "negative_basic", negcat="validation_failure"),
        _tc("TC-ADD-002", "add", "negative_basic", negcat="validation_failure"),
    ]
    adapter.executor.execute(tcs=tcs, config=cfg, run_dir=tmp, progress_cb=_cb,
                             is_paused=lambda: False, is_stopped=lambda: False)
    annotate_grades(tcs, adapter)
    for tc in tcs:
        print(f"  [{tc['result'].upper():8}] {tc['tc_id']:12} {tc['소분류']:16} "
              f"grade={tc.get('automation_grade')} :: {tc['actual']}")
    return tcs


# ─────────────────────────────────────────────────────────────────────────────
# 2) api_rest — 로컬 실제 HTTP 서버
# ─────────────────────────────────────────────────────────────────────────────
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
    def log_message(self, *a):  # 조용히
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
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw or b"{}")
        except Exception:
            data = {}
        if "name" not in data:
            self._send(400, b'{"error": "name required"}')
        else:
            self._send(201, b'{"id": 1}')


def demo_api_rest(tmp: Path) -> list[dict]:
    print("\n=== [2] api_rest / 로컬 실제 HTTP 서버 ===")
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    print("  로컬 서버 기동:", base)

    spec_path = tmp / "openapi.json"
    spec_path.write_text(json.dumps(_OPENAPI), encoding="utf-8")
    cfg = SimpleNamespace(target_config={"openapi_path": str(spec_path), "base_url": base})
    adapter = get_adapter("api_rest")

    spec = adapter.probe.scan(config=cfg, llm=None, run_dir=tmp,
                              progress_cb=_cb, should_stop=lambda: False)
    print("  [Probe] 엔드포인트(leaf):", [f["category_leaf"] for f in spec["features"]])

    tcs = [
        _tc("TC-API-001", "POST /items", "happy_path", "201 생성"),
        _tc("TC-API-002", "POST /items", "negative_basic", "필수값 누락 400", "validation_failure"),
        _tc("TC-API-003", "GET /items", "happy_path", "목록 200"),
        _tc("TC-API-004", "GET /items/{id}", "happy_path", "단건 200"),
    ]
    adapter.executor.execute(tcs=tcs, config=cfg, run_dir=tmp, progress_cb=_cb,
                             is_paused=lambda: False, is_stopped=lambda: False)
    annotate_grades(tcs, adapter)
    for tc in tcs:
        print(f"  [{tc['result'].upper():8}] {tc['tc_id']:12} {tc['소분류']:16} "
              f"grade={tc.get('automation_grade')} :: {tc['actual'][:60]}")
    server.shutdown()
    return tcs


def main() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        all_tcs = demo_api_code(tmp) + demo_api_rest(tmp)
        report = build_report_md(all_tcs, meta={"run_id": "demo", "target_kind": "api_code+api_rest"})
        out = tmp / "test_report.md"
        out.write_text(report, encoding="utf-8")
        print("\n=== [3] 보고서 요약 (report_summary) ===")
        print(report)


if __name__ == "__main__":
    main()
