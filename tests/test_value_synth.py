"""value_synth (D62·D67) — 이름/타입/format 휴리스틱 값 합성 (매뉴얼 무의존)."""
from __future__ import annotations

from app.adapters import value_synth as vs


def test_valid_by_name_hint():
    assert vs.valid_value("email", "str") == "test@example.com"
    assert vs.valid_value("user_email", "string") == "test@example.com"
    assert vs.valid_value("homepage_url", "str") == "https://example.com"
    assert vs.valid_value("created_at", "str") == "2026-01-01"
    assert vs.valid_value("username", "str") == "테스트"


def test_valid_by_type():
    assert vs.valid_value("x", "int") == 1
    assert vs.valid_value("ratio", "float") == 1.0
    assert vs.valid_value("flag", "bool") is True
    assert vs.valid_value("items", "list") == []
    assert vs.valid_value("opts", "dict") == {}
    assert vs.valid_value("anything", "str") == "test"   # 힌트 없으면 기본


def test_valid_by_format_priority():
    # format이 이름보다 우선
    assert vs.valid_value("x", "string", fmt="email") == "test@example.com"
    assert vs.valid_value("x", "string", fmt="date-time") == "2026-01-01"


def test_invalid_value():
    assert vs.invalid_value("count", "int", None, "validation_failure") == "NOT_A_NUMBER"
    # 이메일 의미 → 형식 위반 문자열
    assert vs.invalid_value("email", "str", None, "validation_failure") == "not-an-email"
    # injection
    assert "OR 1=1" in vs.invalid_value("q", "str", None, "injection_or_security")


def test_boundary_value():
    assert vs.boundary_value("age", "int") == 2 ** 63
    assert len(vs.boundary_value("name", "str")) == 100000
