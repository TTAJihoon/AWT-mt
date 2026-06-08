"""api_code 다언어 러너 (D62, P3) — C 시그니처 파싱 + .NET/Java 지연 의존 처리."""
from __future__ import annotations

import pytest

from app.adapters import api_code_adapter as aca
from app.adapters.api_code.base_runner import synth_call
from app.adapters.api_code.c_runner import CRunner


def test_c_runner_parses_signatures():
    tc = {"signatures": [
        {"name": "add", "restype": "int", "argtypes": ["int", "int"]},
        {"name": "concat", "restype": "char*", "argtypes": ["char*", "char*"]},
    ]}
    syms = {s.symbol: s for s in CRunner().list_symbols(tc)}
    assert set(syms) == {"add", "concat"}
    assert syms["add"].params[0]["annotation"] == "int"
    assert syms["add"].params[0]["required"] is True
    assert syms["concat"].returns == "char*"


def test_c_arg_synthesis():
    sym = CRunner().list_symbols(
        {"signatures": [{"name": "add", "restype": "int", "argtypes": ["int", "int"]}]})[0]
    pos, expect_exc = synth_call(sym, "happy_path", "")
    assert pos == {"arg0": 1, "arg1": 1} and expect_exc is False
    neg, expect_exc = synth_call(sym, "negative_basic", "validation_failure")
    assert neg["arg0"] == "NOT_A_NUMBER" and expect_exc is True


def test_get_runner_routing():
    assert aca._get_runner("c").lang == "c"
    assert aca._get_runner("python").lang == "python"
    assert aca._get_runner("dotnet").lang == "dotnet"
    assert aca._get_runner("java").lang == "java"
    with pytest.raises(ValueError):
        aca._get_runner("cobol")


def test_dotnet_java_missing_deps_raise_clear_message():
    # pythonnet/JPype1 미설치 환경 — 호출 시 친절한 안내 예외
    dn = aca._get_runner("dotnet")
    with pytest.raises(RuntimeError, match="pythonnet"):
        dn.list_symbols({"dll_path": "x.dll"})
    jv = aca._get_runner("java")
    with pytest.raises(RuntimeError, match="JPype1"):
        jv.list_symbols({"classpath": "x.jar", "classes": ["X"]})
