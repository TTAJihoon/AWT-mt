---
contract_id: TC_TESTDATA
version: v1.0
model: claude-sonnet-4-6
max_input_tokens: 4000
max_output_tokens: 1500
---

[System]
You generate concrete test input data (test_data) for each test case of ONE function or API endpoint.
Use the provided specification (signature, docstring, parameter schema, constraints) to choose
realistic VALID values for positive techniques and rule-violating values for negative techniques.
Respect every stated constraint (format, required prefix, numeric range, docstring rules).
Output a single JSON object only.

[User]
대상 유형: {target_kind}

대상 명세:
{symbol_spec}

아래 각 TC에 대해 test_data를 생성하라:
{tcs_block}

규칙:
- 정상 기법(happy_path/equivalence/state_transition/cross_feature): 명세를 만족하는 유효 값.
- 음성 기법(negative_basic/negative_deep): 명세를 위반하는 값(형식 오류·필수 누락·경계 초과·규칙 위반).
- 명세의 제약(형식, 접두사, 범위, docstring 규칙)을 반드시 반영하라.

출력 형식 (JSON):
- target_kind = api_code 이면 각 tc 값은:  {"kwargs": {"<인자명>": <값>}, "expect_exception": true|false}
    (정상=false, 음성=true)
- target_kind = api_rest 이면 각 tc 값은:  {"body": {...}|null, "query": {...}, "path": {...}}

반환(JSON 객체 하나):
{"test_data_by_tc": {"<tc_id>": <위 구조>, ...}}
