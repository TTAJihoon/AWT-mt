"""api_rest 어댑터 (D61) — Probe/Executor/Oracle 단위 테스트 (httpx MockTransport)."""
from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from app.adapters import api_rest_adapter as ara

_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "t", "version": "1"},
    "servers": [{"url": "http://testserver"}],
    "paths": {
        "/items": {
            "get": {"tags": ["items"], "operationId": "listItems",
                    "summary": "목록", "responses": {"200": {}}},
            "post": {
                "tags": ["items"], "operationId": "createItem", "summary": "생성",
                "requestBody": {"content": {"application/json": {"schema": {
                    "type": "object", "required": ["name"],
                    "properties": {"name": {"type": "string"}},
                }}}},
                "responses": {"201": {}, "400": {}},
            },
        },
        "/items/{id}": {
            "get": {"tags": ["items"], "operationId": "getItem",
                    "parameters": [{"name": "id", "in": "path", "required": True,
                                    "schema": {"type": "integer"}}],
                    "responses": {"200": {}, "404": {}}},
        },
    },
}


def _write_spec(tmp_path):
    p = tmp_path / "openapi.json"
    p.write_text(json.dumps(_SPEC), encoding="utf-8")
    return str(p)


def _cfg(tmp_path):
    return SimpleNamespace(target_config={
        "openapi_path": _write_spec(tmp_path),
        "base_url": "http://testserver",
    })


def test_probe_builds_one_leaf_per_endpoint(tmp_path):
    probe = ara.ApiRestProbe()
    spec = probe.scan(config=_cfg(tmp_path), llm=None, run_dir=tmp_path,
                      progress_cb=lambda m: None, should_stop=lambda: False)
    leaves = {f["category_leaf"] for f in spec["features"]}
    assert leaves == {"GET /items", "POST /items", "GET /items/{id}"}
    assert spec["pages_scanned"] == 3
    # implicit_spec에 필수 본문 필드가 드러나야 함(LLM이 negative 설계 가능)
    post = next(f for f in spec["features"] if f["category_leaf"] == "POST /items")
    assert "name" in post["implicit_spec"]


def _handler(request: httpx.Request) -> httpx.Response:
    path, method = request.url.path, request.method
    if method == "GET" and path == "/items":
        return httpx.Response(200, json={"items": []})
    if method == "POST" and path == "/items":
        data = json.loads(request.content or b"{}")
        if "name" not in data:
            return httpx.Response(400, json={"error": "name required"})
        return httpx.Response(201, json={"id": 1, **data})
    if method == "GET" and path.startswith("/items/"):
        return httpx.Response(200, json={"id": 1})
    return httpx.Response(404)


@pytest.fixture
def _mock_httpx(monkeypatch):
    real = httpx.Client
    monkeypatch.setattr(
        httpx, "Client",
        lambda **kw: real(transport=httpx.MockTransport(_handler), **kw),
    )


def _tc(tc_id, leaf, tech, expected, negcat=""):
    return {"tc_id": tc_id, "소분류": leaf, "design_technique": tech,
            "negative_category": negcat, "expected": expected,
            "review_status": "approved"}


def test_executor_happy_and_negative(tmp_path, _mock_httpx):
    tcs = [
        _tc("TC-001-001", "POST /items", "happy_path", "201 생성 성공"),
        _tc("TC-001-002", "POST /items", "negative_basic",
            "필수값 누락 시 400", "validation_failure"),
        _tc("TC-002-001", "GET /items", "happy_path", "목록 200"),
        _tc("TC-003-001", "GET /items/{id}", "happy_path", "단건 조회 성공"),
        _tc("TC-099-001", "PATCH /unknown", "happy_path", "흐름형"),  # 매핑 실패
    ]
    out = ara.ApiRestExecutor().execute(
        tcs=tcs, config=_cfg(tmp_path), run_dir=tmp_path,
        progress_cb=lambda m: None, is_paused=lambda: False, is_stopped=lambda: False)
    by = {tc["tc_id"]: tc for tc in out}
    assert by["TC-001-001"]["result"] == "pass"   # 201 ∈ 2xx
    assert by["TC-001-002"]["result"] == "pass"   # 누락→400 ∈ 4xx (기대 일치)
    assert by["TC-002-001"]["result"] == "pass"
    assert by["TC-003-001"]["result"] == "pass"   # path param 치환
    assert by["TC-099-001"]["result"] == "blocked"  # 엔드포인트 매핑 실패


def test_oracle_status_mismatch_is_fail(tmp_path, _mock_httpx):
    # POST 정상 본문인데 happy인데도 서버가 400을 주면 fail이어야 함 → 여기선 반대로
    # 잘못된 기대(2xx인데 4xx 명시)로 fail 확인
    tc = _tc("TC-001-003", "POST /items", "happy_path", "응답 404 기대")
    out = ara.ApiRestExecutor().execute(
        tcs=[tc], config=_cfg(tmp_path), run_dir=tmp_path,
        progress_cb=lambda m: None, is_paused=lambda: False, is_stopped=lambda: False)
    assert out[0]["result"] == "fail"   # 실제 201 vs 명시 404


def test_grade_and_locator():
    adapter = ara._factory()
    assert adapter.locator.stability({"explicit": True}) == 0.95
    assert adapter.negative_category_map({"category_leaf": "POST /items"}).count("validation_failure") == 1
    g, _ = adapter.grade_rules({"result": "pass"}, adapter)
    assert g == "A"
    g2, note = adapter.grade_rules({"result": "blocked", "actual": "엔드포인트 매핑 실패"}, adapter)
    assert g2 == "C" and note
