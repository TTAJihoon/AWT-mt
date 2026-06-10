"""테스트용 로컬 REST API (검증·인증·404를 제대로 구현) — AWT-MT api_rest 시험용.

추가 설치 불필요(파이썬 표준 라이브러리만). 기본 포트 8000.
실행:  python scripts/sample_rest_api.py   (종료: Ctrl+C)

엔드포인트
  GET    /items            아이템 목록 (공개)
  POST   /items            아이템 생성 (Bearer 인증 + name 필수/형식/길이 검증)
  GET    /items/{id}       단건 조회 (정수 id, 없으면 404)
  DELETE /items/{id}       삭제 (Bearer 인증, 없으면 404)
  GET    /openapi.json     OpenAPI 3.0 스펙

인증 토큰:  testtoken   (Authorization: Bearer testtoken)

AWT-MT 위저드 입력값
  대상 유형 : REST API (OpenAPI)
  OpenAPI   : http://localhost:8000/openapi.json
  Base URL  : http://localhost:8000
  인증 토큰 : testtoken
"""
from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8000
TOKEN = "testtoken"

_items: dict[int, dict] = {1: {"id": 1, "name": "샘플 아이템"}}
_next_id = [2]
_lock = threading.Lock()

OPENAPI = {
    "openapi": "3.0.0",
    "info": {"title": "AWT 테스트 API", "version": "1.0.0"},
    "servers": [{"url": f"http://localhost:{PORT}"}],
    "components": {
        "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}},
        "schemas": {
            "Item": {
                "type": "object", "required": ["name"],
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string", "maxLength": 50, "example": "노트북"},
                },
            }
        },
    },
    "paths": {
        "/items": {
            "get": {"tags": ["items"], "operationId": "listItems",
                    "summary": "아이템 목록 조회", "responses": {"200": {"description": "목록"}}},
            "post": {
                "tags": ["items"], "operationId": "createItem", "summary": "아이템 생성",
                "security": [{"bearerAuth": []}],
                "requestBody": {"required": True, "content": {"application/json": {
                    "schema": {"$ref": "#/components/schemas/Item"}}}},
                "responses": {"201": {"description": "생성됨"},
                              "400": {"description": "검증 실패"},
                              "401": {"description": "인증 필요"}},
            },
        },
        "/items/{id}": {
            "get": {"tags": ["items"], "operationId": "getItem", "summary": "아이템 단건 조회",
                    "parameters": [{"name": "id", "in": "path", "required": True,
                                    "schema": {"type": "integer"}}],
                    "responses": {"200": {"description": "조회됨"},
                                  "404": {"description": "없음"}}},
            "delete": {"tags": ["items"], "operationId": "deleteItem", "summary": "아이템 삭제",
                       "security": [{"bearerAuth": []}],
                       "parameters": [{"name": "id", "in": "path", "required": True,
                                       "schema": {"type": "integer"}}],
                       "responses": {"204": {"description": "삭제됨"},
                                     "401": {"description": "인증 필요"},
                                     "404": {"description": "없음"}}},
        },
    },
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # 콘솔에 간단 로그
        print(f"  {self.command} {self.path} -> {args[1] if len(args) > 1 else ''}")

    def _send(self, code, obj=None):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8") if obj is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _auth_ok(self) -> bool:
        return self.headers.get("Authorization", "") == f"Bearer {TOKEN}"

    # ── GET ──────────────────────────────────────────────────────────────
    def do_GET(self):
        if self.path == "/openapi.json":
            return self._send(200, OPENAPI)
        if self.path == "/items":
            with _lock:
                return self._send(200, {"items": list(_items.values())})
        m = re.fullmatch(r"/items/([^/]+)", self.path)
        if m:
            raw = m.group(1)
            if not raw.isdigit():
                return self._send(400, {"error": "id must be an integer"})
            with _lock:
                it = _items.get(int(raw))
            return self._send(200, it) if it else self._send(404, {"error": "not found"})
        self._send(404, {"error": "no route"})

    # ── POST ─────────────────────────────────────────────────────────────
    def do_POST(self):
        if self.path != "/items":
            return self._send(404, {"error": "no route"})
        if not self._auth_ok():
            return self._send(401, {"error": "missing/invalid bearer token"})
        n = int(self.headers.get("Content-Length", 0) or 0)
        try:
            data = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._send(400, {"error": "invalid json"})
        name = data.get("name")
        if name is None:
            return self._send(400, {"error": "name is required"})
        if not isinstance(name, str):
            return self._send(400, {"error": "name must be a string"})
        if len(name) > 50:
            return self._send(400, {"error": "name too long (max 50)"})
        with _lock:
            nid = _next_id[0]; _next_id[0] += 1
            _items[nid] = {"id": nid, "name": name}
            created = _items[nid]
        self._send(201, created)

    # ── DELETE ───────────────────────────────────────────────────────────
    def do_DELETE(self):
        m = re.fullmatch(r"/items/([^/]+)", self.path)
        if not m:
            return self._send(404, {"error": "no route"})
        if not self._auth_ok():
            return self._send(401, {"error": "missing/invalid bearer token"})
        raw = m.group(1)
        if not raw.isdigit():
            return self._send(400, {"error": "id must be an integer"})
        with _lock:
            if int(raw) in _items:
                del _items[int(raw)]
                return self._send(204)
        self._send(404, {"error": "not found"})


def main():
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"테스트 REST API 실행 중 → http://localhost:{PORT}")
    print(f"  OpenAPI : http://localhost:{PORT}/openapi.json")
    print(f"  Bearer  : {TOKEN}")
    print("종료: Ctrl+C")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n종료됨")


if __name__ == "__main__":
    main()
