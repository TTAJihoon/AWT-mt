"""api_rest 어댑터 (D61) — REST/HTTP API (OpenAPI/Swagger).

설계 핵심: Probe와 Executor가 동일 OpenAPI 스펙을 파싱한다.
  - Probe   → 엔드포인트 1개 = leaf 1개. category_leaf = "METHOD path" (안정 키).
  - Executor → 같은 스펙을 재파싱해 "METHOD path" 키로 엔드포인트 상세를 복원.
→ leaf/TC 코어 스키마에 target_ref를 끼워넣을 필요가 없어 Stage 1~3 코어 무수정.

오라클(강함): HTTP status 코드 + 응답 JSON. 대부분 자동화 등급 A.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import httpx

from app.adapters.base import ProgressCb, StopFn, TargetAdapter, Verdict
from app.adapters.registry import register

_HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")


# ─────────────────────────────────────────────────────────────────────────────
# OpenAPI 로드 & 파싱
# ─────────────────────────────────────────────────────────────────────────────
def _load_spec(target_config: dict) -> dict:
    """openapi_path(파일) 또는 openapi_url에서 스펙 로드(JSON/YAML)."""
    path = target_config.get("openapi_path")
    url = target_config.get("openapi_url")
    if path:
        text = Path(path).read_text(encoding="utf-8")
    elif url:
        resp = httpx.get(url, timeout=30.0)
        resp.raise_for_status()
        text = resp.text
    else:
        raise ValueError("api_rest: target_config에 openapi_path 또는 openapi_url 필요")
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    import yaml
    return yaml.safe_load(text)


def _resolve_ref(spec: dict, node: Any) -> Any:
    """$ref 1단계 해소(components/schemas 등). 순환은 얕게 처리."""
    seen = 0
    while isinstance(node, dict) and "$ref" in node and seen < 10:
        ref = node["$ref"]
        if not ref.startswith("#/"):
            return node
        cur: Any = spec
        for part in ref[2:].split("/"):
            cur = cur.get(part, {}) if isinstance(cur, dict) else {}
        node = cur
        seen += 1
    return node


def _base_url(spec: dict, target_config: dict) -> str:
    if target_config.get("base_url"):
        return str(target_config["base_url"]).rstrip("/")
    servers = spec.get("servers") or []
    if servers and isinstance(servers, list) and servers[0].get("url"):
        return str(servers[0]["url"]).rstrip("/")
    return ""


def _endpoint_key(method: str, path: str) -> str:
    return f"{method.upper()} {path}"


def _iter_operations(spec: dict):
    """(method, path, operation, path_level_params) 생성."""
    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        path_params = item.get("parameters", []) or []
        for method in _HTTP_METHODS:
            op = item.get(method)
            if isinstance(op, dict):
                yield method, path, op, path_params


def _build_endpoint_map(spec: dict) -> dict[str, dict]:
    """'METHOD path' → target_ref(엔드포인트 상세)."""
    emap: dict[str, dict] = {}
    for method, path, op, path_params in _iter_operations(spec):
        params = list(path_params) + list(op.get("parameters", []) or [])
        params = [_resolve_ref(spec, p) for p in params]
        body_schema = None
        content_type = None
        rb = op.get("requestBody")
        if rb:
            rb = _resolve_ref(spec, rb)
            content = rb.get("content", {})
            for ct in ("application/json", *content.keys()):
                if ct in content:
                    body_schema = _resolve_ref(spec, content[ct].get("schema", {}))
                    content_type = ct
                    break
        emap[_endpoint_key(method, path)] = {
            "method": method.upper(),
            "path": path,
            "operation_id": op.get("operationId") or _endpoint_key(method, path),
            "summary": (op.get("summary") or op.get("description") or "").strip(),
            "parameters": params,
            "request_body_schema": body_schema,
            "content_type": content_type,
            "responses": list((op.get("responses") or {}).keys()),
            "security": op.get("security"),
            "tags": op.get("tags") or ["default"],
        }
    return emap


def _spec_summary(ref: dict, spec: dict) -> str:
    """leaf implicit_spec 텍스트 — 파라미터/본문/응답을 사람이 읽을 형태로."""
    lines = [ref.get("summary", "") or f"{ref['method']} {ref['path']} 엔드포인트"]
    req = [p for p in ref["parameters"] if p.get("required")]
    if req:
        names = ", ".join(f"{p.get('name')}({(p.get('schema') or {}).get('type','')})" for p in req)
        lines.append(f"필수 파라미터: {names}")
    if ref.get("request_body_schema"):
        props = (ref["request_body_schema"].get("properties") or {})
        if props:
            lines.append("요청 본문 필드: " + ", ".join(props.keys()))
        reqd = ref["request_body_schema"].get("required")
        if reqd:
            lines.append("필수 본문 필드: " + ", ".join(reqd))
    if ref.get("responses"):
        lines.append("응답 코드: " + ", ".join(str(r) for r in ref["responses"]))
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 스키마 → 예시/오류 페이로드 합성
# ─────────────────────────────────────────────────────────────────────────────
def _example_from_schema(schema: Any, spec: dict, depth: int = 0) -> Any:
    if not isinstance(schema, dict) or depth > 6:
        return "string"
    schema = _resolve_ref(spec, schema)
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    if schema.get("enum"):
        return schema["enum"][0]
    t = schema.get("type")
    if t == "object" or schema.get("properties"):
        out = {}
        props = schema.get("properties") or {}
        required = set(schema.get("required") or list(props.keys()))
        for name, sub in props.items():
            if name in required:
                out[name] = _example_from_schema(sub, spec, depth + 1)
        return out
    if t == "array":
        return [_example_from_schema(schema.get("items", {}), spec, depth + 1)]
    if t in ("integer", "number"):
        mn = schema.get("minimum")
        return (mn if isinstance(mn, (int, float)) else 1)
    if t == "boolean":
        return True
    # string + format
    fmt = schema.get("format", "")
    return {
        "email": "test@example.com",
        "date": "2026-01-01",
        "date-time": "2026-01-01T00:00:00Z",
        "uuid": "00000000-0000-0000-0000-000000000000",
        "uri": "https://example.com",
        "password": "Passw0rd!",
    }.get(fmt, "string")


def _invalid_body(schema: Any, spec: dict, category: str) -> Any:
    """negative 카테고리에 맞는 잘못된 본문 합성."""
    valid = _example_from_schema(schema, spec)
    if not isinstance(valid, dict):
        return valid
    schema = _resolve_ref(spec, schema) if isinstance(schema, dict) else {}
    required = list(schema.get("required") or list(valid.keys()))
    if category == "validation_failure" and required:
        bad = dict(valid)
        bad.pop(required[0], None)          # 필수 필드 누락
        return bad
    if category == "boundary_violation":
        bad = dict(valid)
        for k, v in bad.items():
            if isinstance(v, str):
                bad[k] = "x" * 100000        # 과대 길이
                break
            if isinstance(v, int):
                bad[k] = 2 ** 63
                break
        return bad
    if category == "injection_or_security":
        bad = dict(valid)
        for k, v in bad.items():
            if isinstance(v, str):
                bad[k] = "' OR 1=1; DROP TABLE users;--"
                break
        return bad
    # duplicate_or_conflict 등은 유효 본문 그대로(서버가 충돌 판정)
    return valid


# ─────────────────────────────────────────────────────────────────────────────
# 기대 status 추론
# ─────────────────────────────────────────────────────────────────────────────
_POSITIVE_TECH = {"happy_path", "equivalence", "state_transition", "cross_feature"}


def _expected_status_class(tc: dict) -> tuple[str, int | None]:
    """(class, explicit_code). class ∈ {'2xx','4xx','any'}."""
    expected = str(tc.get("expected", ""))
    m = re.search(r"\b([1-5]\d{2})\b", expected)
    explicit = int(m.group(1)) if m else None
    tech = tc.get("design_technique", "")
    negcat = tc.get("negative_category", "")
    if explicit:
        return (f"{explicit // 100}xx", explicit)
    if tech in _POSITIVE_TECH or not tech:
        return ("2xx", None)
    # negative → 4xx (카테고리별 세분)
    return ("4xx", {
        "permission_denied": 401,
        "validation_failure": 400,
        "boundary_violation": 400,
        "duplicate_or_conflict": 409,
    }.get(negcat))


# ─────────────────────────────────────────────────────────────────────────────
# Oracle
# ─────────────────────────────────────────────────────────────────────────────
class RestOracle:
    def verify(self, expected: str, actual: Any, methods: list[str]) -> Verdict:
        # actual = {"status": int, "body": str, "tc": dict, "error": str|None}
        if actual.get("error"):
            return Verdict("blocked", 0.2, actual["error"], [])
        status = actual.get("status")
        cls, explicit = _expected_status_class(actual["tc"])
        ok = False
        if explicit is not None:
            ok = (status == explicit) or (status // 100 == explicit // 100)
        else:
            ok = (f"{status // 100}xx" == cls)
        conf = 0.9 if explicit is not None else 0.78
        msg = f"HTTP {status} (기대 {explicit or cls})"
        return Verdict("pass" if ok else "fail", conf, msg, [actual.get("body", "")[:300]])


# ─────────────────────────────────────────────────────────────────────────────
# Probe
# ─────────────────────────────────────────────────────────────────────────────
class ApiRestProbe:
    def scan(self, *, config: Any, llm: Any, run_dir: Path,
             progress_cb: ProgressCb, should_stop: StopFn):
        spec = _load_spec(config.target_config)
        base = _base_url(spec, config.target_config)
        emap = _build_endpoint_map(spec)
        progress_cb(f"  OpenAPI 파싱 — 엔드포인트 {len(emap)}개 (base={base or '미지정'})")

        features = []
        for key, ref in emap.items():
            features.append({
                "category_major": (ref["tags"][0] if ref["tags"] else "API"),
                "category_mid": ref["path"].strip("/").split("/")[0] or "root",
                "category_leaf": key,                       # "METHOD path" — 안정 키
                "implicit_spec": _spec_summary(ref, spec),
                "confidence": "HIGH",
                "source_url": ref["tags"][0] if ref["tags"] else "API",
                "source_element": ref["operation_id"],
            })
        # 스펙 동결(추적성)
        out = run_dir / "api-scan"
        out.mkdir(parents=True, exist_ok=True)
        (out / "openapi.json").write_text(
            json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "target": base, "openapi": True,
            "pages_scanned": len(features), "features": features,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Executor
# ─────────────────────────────────────────────────────────────────────────────
def _apply_auth(headers: dict, params: dict, auth: dict | None, skip: bool) -> None:
    """auth 설정을 헤더/쿼리에 반영. skip=True면 인증 누락(권한 거부 시험용)."""
    if not auth or skip:
        return
    t = auth.get("type", "")
    if t == "bearer":
        headers["Authorization"] = f"Bearer {auth.get('token','')}"
    elif t == "basic":
        import base64
        raw = f"{auth.get('user','')}:{auth.get('password','')}".encode()
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode()
    elif t == "header":
        headers[auth.get("name", "X-API-Key")] = auth.get("value", "")
    elif t == "apikey":
        if auth.get("in") == "query":
            params[auth.get("name", "api_key")] = auth.get("value", "")
        else:
            headers[auth.get("name", "X-API-Key")] = auth.get("value", "")


def _fill_path(path: str, params: list[dict], spec: dict) -> str:
    def repl(m):
        name = m.group(1)
        for p in params:
            if p.get("name") == name and p.get("in") == "path":
                return str(_example_from_schema(p.get("schema", {}), spec))
        return "1"
    return re.sub(r"\{([^}]+)\}", repl, path)


class ApiRestExecutor:
    def execute(self, *, tcs: list[dict], config: Any, run_dir: Path,
                progress_cb: ProgressCb, is_paused: StopFn, is_stopped: StopFn):
        spec = _load_spec(config.target_config)
        base = _base_url(spec, config.target_config)
        emap = _build_endpoint_map(spec)
        auth = (config.target_config or {}).get("auth")
        oracle = RestOracle()
        timeout = float((config.target_config or {}).get("timeout", 30.0))

        runnable = [tc for tc in tcs if tc.get("review_status") in ("approved", "edited")]
        progress_cb(f"Stage 5(api_rest): {len(runnable)}개 TC 실행 (base={base})")

        with httpx.Client(base_url=base, timeout=timeout, follow_redirects=True) as client:
            for i, tc in enumerate(runnable, 1):
                if is_stopped and is_stopped():
                    progress_cb(f"⏹ 중단 — {i-1}/{len(runnable)} 실행 후 종료")
                    break
                key = (tc.get("소분류") or "").strip()
                ref = emap.get(key)
                if not ref:
                    tc["result"] = "blocked"
                    tc["actual"] = f"엔드포인트 매핑 실패: {key!r} (흐름형/비표준 TC)"
                    tc["exec_confidence"] = 0.2
                    continue
                self._run_one(client, tc, ref, spec, auth, oracle, progress_cb)
                progress_cb(f"  ({i}/{len(runnable)}) {tc['tc_id']} {key} → {tc.get('result')}")

        for tc in tcs:
            if tc.get("review_status") not in ("approved", "edited"):
                tc["result"] = "not_executed"
        progress_cb("Stage 5(api_rest) 완료")
        return tcs

    def _run_one(self, client, tc, ref, spec, auth, oracle, progress_cb):
        start = time.time()
        tech = tc.get("design_technique", "")
        negcat = tc.get("negative_category", "")
        is_negative = tech not in _POSITIVE_TECH and tech != ""
        headers: dict = {}
        query: dict = {}
        # test_data 우선(LLM/사용자 제공): {"body":..,"query":{..},"path":{..}}
        td = tc.get("test_data") if isinstance(tc.get("test_data"), dict) else {}
        # 쿼리 파라미터(필수) 채움
        for p in ref["parameters"]:
            if p.get("in") == "query" and p.get("required"):
                query[p["name"]] = _example_from_schema(p.get("schema", {}), spec)
        query.update(td.get("query") or {})
        # 인증: permission_denied 시험이면 인증 누락
        skip_auth = (negcat == "permission_denied")
        _apply_auth(headers, query, auth, skip_auth)
        # 본문 합성 (test_data.body 우선)
        body = None
        if "body" in td:
            body = td["body"]
        elif ref.get("request_body_schema") is not None:
            if is_negative and negcat in (
                "validation_failure", "boundary_violation", "injection_or_security"):
                body = _invalid_body(ref["request_body_schema"], spec, negcat)
            else:
                body = _example_from_schema(ref["request_body_schema"], spec)
        url = _fill_path(ref["path"], ref["parameters"], spec)
        for k, v in (td.get("path") or {}).items():
            url = url.replace("{" + k + "}", str(v))
        try:
            resp = client.request(
                ref["method"], url,
                params=query or None,
                json=body if body is not None else None,
                headers=headers or None,
            )
            actual = {"status": resp.status_code, "body": resp.text, "tc": tc, "error": None}
        except Exception as e:  # 연결 실패 등
            actual = {"status": None, "body": "", "tc": tc, "error": f"요청 실패: {e}"}

        verdict = oracle.verify(tc.get("expected", ""), actual, tc.get("verification_methods", []))
        tc["result"] = verdict.status
        tc["actual"] = verdict.actual + (f" | {actual['body'][:200]}" if actual.get("body") else "")
        tc["exec_confidence"] = round(verdict.confidence - (time.time() - start) * 0.001, 2)
        tc["target_ref"] = {"method": ref["method"], "path": ref["path"],
                            "operation_id": ref["operation_id"], "explicit": True}


# ─────────────────────────────────────────────────────────────────────────────
# Locator / grade / negative-map / factory
# ─────────────────────────────────────────────────────────────────────────────
class _RestLocator:
    def stability(self, target_ref: dict) -> float:
        return 0.95 if target_ref.get("explicit") else 0.85


def _rest_negative_map(leaf: dict) -> list[str]:
    key = (leaf.get("category_leaf") or "")
    method = key.split(" ", 1)[0].upper()
    if method in ("POST", "PUT", "PATCH"):
        return ["validation_failure", "boundary_violation",
                "duplicate_or_conflict", "permission_denied", "injection_or_security"]
    if method == "DELETE":
        return ["permission_denied", "duplicate_or_conflict"]
    return ["permission_denied", "injection_or_security"]  # GET 등


def _rest_grade(tc: dict, adapter: TargetAdapter) -> tuple[str, str]:
    # REST: status/응답 오라클이 객관적 → A. 매핑 실패(흐름형)는 C(다중 엔드포인트 수동).
    if tc.get("result") == "blocked" and "매핑 실패" in str(tc.get("actual", "")):
        return "C", "다중 엔드포인트 흐름 — 수동 시퀀스 확인 필요"
    return "A", ""


def _factory() -> TargetAdapter:
    return TargetAdapter(
        target_kind="api_rest",
        probe=ApiRestProbe(),
        executor=ApiRestExecutor(),
        locator=_RestLocator(),
        oracle=RestOracle(),
        negative_category_map=_rest_negative_map,
        grade_rules=_rest_grade,
        label="REST API (OpenAPI)",
    )


register("api_rest", _factory, label="REST API (OpenAPI)")
