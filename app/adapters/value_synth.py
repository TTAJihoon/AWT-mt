"""파라미터 값 합성 (D62·D67) — 매뉴얼 산문 없이도 동작.

이름(name) + 타입(type) + format 휴리스틱으로 유효/경계/오류 값을 생성한다.
REST(OpenAPI)·코드 라이브러리 실행기가 공유. "email: str"처럼 타입만으론
모르는 의미를 *이름*으로 보완한다(generic "test"가 이메일 검증을 깨던 문제 해결).

우선순위: TC가 test_data를 직접 제공하면 그것이 최우선(이 모듈은 폴백).
LLM test_data 생성(llm_test_data.py)이 있으면 그 다음, 마지막이 본 휴리스틱.
"""
from __future__ import annotations

# 이름 키워드 → 의미 카테고리
_NAME_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("email", "e_mail", "mail"), "email"),
    (("url", "uri", "href", "link", "endpoint", "webhook"), "url"),
    (("uuid", "guid"), "uuid"),
    (("birth", "dob", "date", "_at", "time", "timestamp", "expires"), "date"),
    (("phone", "tel", "mobile", "cell"), "phone"),
    (("password", "passwd", "pwd", "secret"), "password"),
    (("zip", "postal"), "zipcode"),
    (("ip",), "ip"),
    (("name", "title", "username", "user", "nick", "label"), "name"),
]

_VALID: dict[str, object] = {
    "email": "test@example.com",
    "url": "https://example.com",
    "uuid": "00000000-0000-0000-0000-000000000000",
    "date": "2026-01-01",
    "phone": "010-1234-5678",
    "password": "Passw0rd!",
    "zipcode": "12345",
    "ip": "127.0.0.1",
    "name": "테스트",
}

# format 위반(=유효하지 않은) 값 — validation_failure 시험용
_INVALID_FORMAT: dict[str, object] = {
    "email": "not-an-email",
    "url": "not a url",
    "uuid": "xxxx",
    "date": "2026-13-99",
    "phone": "abc",
    "ip": "999.999.999.999",
}


def _is_int(a: str) -> bool:
    return any(t in a for t in ("int", "long", "int32", "int64", "integer")) and "point" not in a


def _is_float(a: str) -> bool:
    return any(t in a for t in ("float", "double", "decimal", "number", "single"))


def _category(name: str, fmt: str | None) -> str | None:
    """format 우선, 없으면 이름 키워드로 의미 카테고리 추론."""
    f = (fmt or "").lower()
    if f in ("email", "uri", "url", "uuid", "date", "date-time", "ipv4", "password"):
        return {"uri": "url", "date-time": "date", "ipv4": "ip"}.get(f, f if f != "url" else "url")
    n = (name or "").lower()
    for keys, cat in _NAME_HINTS:
        if any(k in n for k in keys):
            return cat
    return None


def valid_value(name: str, type_str: str, fmt: str | None = None):
    a = (type_str or "").lower()
    if "bool" in a:
        return True
    if _is_int(a):
        return 1
    if _is_float(a):
        return 1.0
    if any(t in a for t in ("list", "array", "[]", "sequence")):
        return []
    if any(t in a for t in ("dict", "map", "object")):
        return {}
    # 문자열/미상 → 이름·format 의미 반영
    cat = _category(name, fmt)
    if cat and cat in _VALID:
        return _VALID[cat]
    return "test"


def invalid_value(name: str, type_str: str, fmt: str | None, category: str):
    """validation_failure / injection 시험용 위반 값."""
    a = (type_str or "").lower()
    if category == "injection_or_security":
        return "' OR 1=1; DROP TABLE users;--"
    # 숫자/불리언 타입엔 문자열을 넣어 타입 위반
    if _is_int(a) or _is_float(a):
        return "NOT_A_NUMBER"
    if "bool" in a:
        return "NOT_A_BOOL"
    # 문자열: format/이름 의미가 있으면 그 형식을 위반
    cat = _category(name, fmt)
    if cat and cat in _INVALID_FORMAT:
        return _INVALID_FORMAT[cat]
    return object()   # 임의 객체 — 문자열 기대 위반


def boundary_value(name: str, type_str: str, fmt: str | None = None):
    a = (type_str or "").lower()
    if _is_int(a) or _is_float(a):
        return 2 ** 63
    if any(t in a for t in ("str", "string", "char", "text")) or not a:
        return "x" * 100000
    return None
