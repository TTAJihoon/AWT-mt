"""api_code 어댑터 (D62) — Python 러너 Probe/Executor/Oracle 테스트."""
from __future__ import annotations

from types import SimpleNamespace

from app.adapters import api_code_adapter as aca

_MODULE_SRC = '''
def add(a: int, b: int) -> int:
    """두 정수의 합."""
    return a + b

def greet(name: str) -> str:
    return f"hi {name}"

def needs_nothing() -> int:
    return 42

def _private(x):
    return x
'''


def _cfg(tmp_path):
    p = tmp_path / "mylib.py"
    p.write_text(_MODULE_SRC, encoding="utf-8")
    return SimpleNamespace(target_config={"lang": "python", "module_path": str(p)})


def test_probe_lists_public_functions(tmp_path):
    spec = aca.ApiCodeProbe().scan(config=_cfg(tmp_path), llm=None, run_dir=tmp_path,
                                   progress_cb=lambda m: None, should_stop=lambda: False)
    leaves = {f["category_leaf"] for f in spec["features"]}
    assert leaves == {"add", "greet", "needs_nothing"}   # _private 제외
    add = next(f for f in spec["features"] if f["category_leaf"] == "add")
    assert "필수 인자: a, b" in add["implicit_spec"]


def _tc(tc_id, leaf, tech, negcat=""):
    return {"tc_id": tc_id, "소분류": leaf, "design_technique": tech,
            "negative_category": negcat, "expected": "", "review_status": "approved"}


def test_executor_positive_negative_and_blocked(tmp_path):
    tcs = [
        _tc("TC-001-001", "add", "happy_path"),
        _tc("TC-001-002", "add", "negative_basic", "validation_failure"),
        _tc("TC-002-001", "greet", "happy_path"),
        _tc("TC-003-001", "needs_nothing", "negative_basic", "validation_failure"),
        _tc("TC-099-001", "nope", "happy_path"),
    ]
    out = aca.ApiCodeExecutor().execute(
        tcs=tcs, config=_cfg(tmp_path), run_dir=tmp_path,
        progress_cb=lambda m: None, is_paused=lambda: False, is_stopped=lambda: False)
    by = {tc["tc_id"]: tc for tc in out}
    assert by["TC-001-001"]["result"] == "pass"    # add(1,1)=2 정상
    assert by["TC-001-002"]["result"] == "pass"    # add("NOT_A_NUMBER",1) → TypeError 기대대로
    assert by["TC-002-001"]["result"] == "pass"    # greet("test")
    assert by["TC-003-001"]["result"] == "blocked" # 인자 없는 함수 음성 합성 불가
    assert by["TC-099-001"]["result"] == "blocked" # 심볼 매핑 실패


def test_grade_and_negmap():
    adapter = aca._factory()
    assert adapter.locator.stability({"explicit": True}) == 0.95
    assert "validation_failure" in adapter.negative_category_map({"category_leaf": "add"})
    assert adapter.grade_rules({"result": "pass"}, adapter)[0] == "A"
    assert adapter.grade_rules({"result": "blocked"}, adapter)[0] == "C"
