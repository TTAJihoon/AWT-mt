"""Mock LLM 클라이언트 — API 호출 없이 TC를 직접 생성 (테스트용).

실제 LLMClient와 동일한 call(contract_id, inputs) 인터페이스를 구현.
그누보드5 기능 명세서 기반으로 TC를 미리 생성해 반환.
"""
from __future__ import annotations
import re
from pathlib import Path


class MockLLMClient:
    """Anthropic API 호출 없이 동작하는 테스트용 LLM 클라이언트."""

    def __init__(self, run_id: str = "mock"):
        self.run_id = run_id
        self._call_count = 0

    def call(self, contract_id: str, inputs: dict, use_cache: bool = True) -> dict:
        self._call_count += 1
        if contract_id == "TC_DESIGN":
            return self._tc_design(inputs)
        if contract_id == "TC_DESIGN_GROUP":     # D54-A
            return self._tc_design_group(inputs)
        if contract_id == "TC_DESIGN_API":       # D59 — API-aware
            return self._tc_design_api(inputs)
        if contract_id == "TC_FLOW":             # D54-B
            return self._tc_flow(inputs)
        if contract_id == "TC_V10_GROUP":        # D56
            return self._tc_v10_group(inputs)
        if contract_id == "TC_REGEN":
            return self._tc_regen(inputs)
        if contract_id == "DOM_SPEC":
            return self._dom_spec(inputs)
        if contract_id == "FAILURE_ANALYSIS":
            return self._failure_analysis(inputs)
        if contract_id == "PATTERN_EXTRACT":
            return self._pattern_extract(inputs)
        return {}

    # ── TC_DESIGN ────────────────────────────────────────────────────────
    def _tc_design(self, inputs: dict) -> dict:
        leaf = inputs.get("category_leaf", "")
        mid = inputs.get("category_mid", "")
        major = inputs.get("category_major", "")
        req_id = inputs.get("requirement_id", "F001")
        tc_start = inputs.get("tc_id_start", "TC-001-001")
        excerpt = inputs.get("manual_excerpt", "")

        # tc_id 시작 번호 파싱
        m = re.match(r"TC-(\d+)-(\d+)", tc_start)
        leaf_num = m.group(1) if m else "001"

        tcs = _GNUBOARD5_TCS.get(leaf, None)
        if tcs is None:
            tcs = _generic_tcs(leaf, mid, major, excerpt)

        # tc_id 재부여
        result = []
        for i, tc in enumerate(tcs, 1):
            t = dict(tc)
            t["tc_id"] = f"TC-{leaf_num}-{i:03d}"
            t["requirement_id"] = req_id
            result.append(t)
        return {"tcs": result}

    # ── TC_DESIGN_GROUP (D54-A) — features_block의 각 기능에 canned TC + leaf_index ──
    def _tc_design_group(self, inputs: dict) -> dict:
        block = inputs.get("features_block", "")
        out: list[dict] = []
        for line in block.splitlines():
            m = re.match(r"^\s*(\d+)\.\s*\[(.*?)\]", line)
            if not m:
                continue
            gi = int(m.group(1))
            parts = [p.strip() for p in m.group(2).split(">")]
            major = parts[0] if parts else ""
            mid   = parts[1] if len(parts) > 1 else ""
            leaf  = parts[-1] if parts else ""
            tcs = _GNUBOARD5_TCS.get(leaf) or _generic_tcs(leaf, mid, major, "")
            for tc in tcs:
                t = dict(tc)
                t["leaf_index"] = gi      # stage2가 leaf로 매핑
                out.append(t)
        return {"tcs": out}

    # ── TC_DESIGN_API (D59) — 엔드포인트/함수 leaf에 API-의미 TC ──────────
    def _tc_design_api(self, inputs: dict) -> dict:
        block = inputs.get("features_block", "")
        out: list[dict] = []
        for line in block.splitlines():
            m = re.match(r"^\s*(\d+)\.\s*\[(.*?)\]", line)
            if not m:
                continue
            gi = int(m.group(1))
            leaf = [p.strip() for p in m.group(2).split(">")][-1]
            method = leaf.split(" ", 1)[0].upper() if " " in leaf else ""
            is_write = method in ("POST", "PUT", "PATCH") or method == ""  # code 함수 포함
            out.append({
                "leaf_index": gi, "scenario": f"{leaf} 정상 호출",
                "precondition": "유효한 입력값 제공",
                "expected": "2xx 응답 또는 정상 반환",
                "design_technique": "happy_path", "negative_category": None,
                "source_quote": "INFERRED: API 정상 흐름",
                "gen_confidence": 0.9, "applied_invariant": None, "related_defect_id": None,
            })
            if is_write:
                out.append({
                    "leaf_index": gi, "scenario": f"{leaf} 필수값 누락/형식 위반",
                    "precondition": "필수 파라미터 누락 또는 타입 오류 입력",
                    "expected": "400 Bad Request 또는 예외 발생",
                    "design_technique": "negative_basic",
                    "negative_category": "validation_failure",
                    "source_quote": "INVARIANT: required_field_empty_rejection",
                    "gen_confidence": 0.8,
                    "applied_invariant": "required_field_empty_rejection",
                    "related_defect_id": None,
                })
        return {"tcs": out}

    # ── TC_FLOW (D54-B) — 회귀 안정성 위해 빈 여정(코드 경로만 통과) ──
    def _tc_flow(self, inputs: dict) -> dict:
        return {"flows": []}

    # ── TC_V10_GROUP (D56) — 누락 카테고리당 음성 TC 1개 + leaf_index ──
    def _tc_v10_group(self, inputs: dict) -> dict:
        block = inputs.get("features_block", "")
        out: list[dict] = []
        cur_gi: int | None = None
        cur_leaf = ""
        _cats = ("validation_failure", "duplicate_or_conflict", "permission_denied",
                 "boundary_violation", "injection_or_security")
        for line in block.splitlines():
            m = re.match(r"^\s*(\d+)\.\s*\[(.*?)\]", line)
            if m:
                cur_gi = int(m.group(1))
                parts = [p.strip() for p in m.group(2).split(">")]
                cur_leaf = parts[-1] if parts else ""
            elif "누락 음성 카테고리" in line and cur_gi is not None:
                for c in [c for c in _cats if c in line]:
                    out.append({
                        "leaf_index": cur_gi,
                        "scenario": f"{cur_leaf} — {c} 음성 케이스",
                        "precondition": "해당 조건 위반 입력",
                        "expected_output": "오류 메시지 표시 또는 차단",
                        "technique": "negative_deep",
                        "negative_category": c,
                        "source_quote": "INVARIANT: required_field_empty_rejection",
                        "gen_confidence": 0.6,
                        "applied_invariant": "required_field_empty_rejection",
                        "related_defect_id": None,
                    })
        return {"tcs": out}

    def _tc_regen(self, inputs: dict) -> dict:
        # 실패 TC를 다시 생성 — 여기서는 source_quote를 INFERRED로 고정해 통과
        failed = eval(inputs.get("failed_tcs_json", "[]"))  # noqa: S307
        fixed = []
        for tc in failed:
            t = dict(tc)
            if not t.get("source_quote"):
                t["source_quote"] = f"INFERRED: {t.get('scenario', '')[:40]}"
            if not t.get("design_technique"):
                t["design_technique"] = "happy_path"
            if not t.get("expected"):
                t["expected"] = "정상 처리 완료"
            fixed.append(t)
        return {"tcs": fixed}

    def _dom_spec(self, inputs: dict) -> dict:
        return {
            "features": [
                {"category_major": "회원 관리", "category_mid": "회원가입", "category_leaf": "정상 가입",
                 "implicit_spec": "아이디 중복 방지", "source_element": "form#fregister", "confidence": 0.95},
                {"category_major": "회원 관리", "category_mid": "로그인", "category_leaf": "정상 로그인",
                 "implicit_spec": "실패 시 오류 메시지", "source_element": "form#flogin", "confidence": 0.93},
                {"category_major": "게시판", "category_mid": "게시글 목록", "category_leaf": "목록 조회",
                 "implicit_spec": "페이지네이션", "source_element": "div.board_list", "confidence": 0.90},
            ]
        }

    def _failure_analysis(self, inputs: dict) -> dict:
        """Mock FAILURE_ANALYSIS — D50 5enum 정확한 값 반환 + source_quote 기반 분류."""
        actual = inputs.get("actual_output", "")
        expected = inputs.get("expected_output", "")
        sq = inputs.get("source_quote", "")

        # D50 enum 5종 자동 분류 (실제 LLM은 prompt 강제로 직접 출력)
        category = "real_defect"  # 기본값
        evidence = "actual ≠ expected, 명료한 oracle"
        if sq.startswith("INFERRED"):
            category = "fictional_positive"
            evidence = f"source_quote가 INFERRED — TC 자체가 가공된 명세 검증 의심"
        elif any(k in actual.lower() for k in ("timeout", "nosuchelement", "요소 없음", "찾을 수 없")):
            category = "selector_broken"
            evidence = f"actual에 자동화 오류 단서 감지"
        elif not expected.strip() or len(expected) < 10:
            category = "expected_mismatch"
            evidence = f"expected가 너무 짧거나 추상적 ({len(expected)}자)"

        return {
            "actual_output_summary": actual[:100] if actual else "페이지 내용 불일치",
            "difference": f"기대: {expected[:60]} / 실제: {actual[:60]}",
            "root_cause_candidates": ["UI 선택자 불일치", "비동기 로딩 타이밍", "권한 부족"],
            "failure_category": category,
            "category_evidence": evidence,
            "retry_history": "없음",
            "exec_confidence": 0.5,
        }

    def _pattern_extract(self, inputs: dict) -> dict:
        """PATTERN_EXTRACT Mock — 결함에서 패턴 제안 자동 생성 시뮬레이션."""
        feature_type = inputs.get("feature_type", "OTHER")
        defect_id = inputs.get("defect_id", "DEF-UNKNOWN")
        return {
            "patternProposal": {
                "name": f"MOCK_PATTERN_{feature_type}",
                "description": f"{feature_type} 기능에서 반복 발생하는 검증 누락 패턴",
                "appliesTo": [feature_type, "UPDATE"] if feature_type != "UPDATE" else [feature_type],
                "checks": [
                    "정상 케이스 수행 후 상태 반영 확인",
                    "비로그인 상태에서 해당 기능 접근 차단 확인",
                    "필수 입력값 빈값 제출 시 오류 메시지 표시 확인",
                ],
                "confidence": 0.75,
            },
            "suggestedInvariant": {
                "name": f"mock_invariant_{feature_type.lower()}",
                "statement": f"{feature_type} 액션은 인증된 사용자만 실행 가능해야 한다",
                "appliesTo": [feature_type],
                "verification": f"{feature_type} 요청 시 세션 유효성 확인",
            },
        }


# ── 그누보드5 사전 정의 TC ────────────────────────────────────────────────

# source_quote v2 — 3단계 형식: MANUAL:<인용> | INVARIANT:<name> | INFERRED:<근거>
_Q: dict[str, str] = {
    "join":   "MANUAL: 아이디, 비밀번호, 이름, 이메일, 닉네임 입력 필수",
    "dup_id": "MANUAL: 아이디: 영문/숫자 조합, 중복 불가, 금지단어 사용 불가",
    "pw_len": "MANUAL: 비밀번호: 최소 6자 이상",
    "email":  "MANUAL: 이메일 형식 검증 필수",
    "agree":  "MANUAL: 약관 및 개인정보처리방침 동의 필수",
    "login":  "MANUAL: 아이디 + 비밀번호로 로그인",
    "fail":   "MANUAL: 로그인 실패 시 오류 메시지 표시",
    "noauth": "MANUAL: 비로그인 상태에서 회원 전용 기능 접근 시 로그인 페이지로 이동",
    "write":  "MANUAL: 비로그인 시 작성 불가 (설정에 따라 비회원 작성 허용 가능)",
    "title":  "MANUAL: 제목 필수, 내용 선택",
    "del":    "MANUAL: 삭제 시 확인 다이얼로그 표시",
    "cmnt":   "MANUAL: 댓글 내용 필수",
    "search": "MANUAL: 제목, 내용, 작성자 검색 가능",
    "perm":   "INVARIANT: auth_gate_mutable_actions",
    "page":   "MANUAL: 게시판별 글 목록 표시 (페이지네이션)",
    "secret": "MANUAL: 비밀글: 작성자·관리자 외 내용 비공개",
    "file":   "MANUAL: 허용 확장자 관리자 설정",
    "point":  "MANUAL: 회원가입, 로그인, 게시글 작성, 댓글 작성 시 포인트 적립",
    "level":  "MANUAL: 회원 레벨 1~10 (10이 최고)",
    "ip":     "MANUAL: 차단된 IP에서 접속 시 접근 불가 메시지 표시",
    "id_len": "MANUAL: 아이디: 3~20자",
    "nick":   "MANUAL: 닉네임: 2~20자 (바이트)",
    # invariant 기반 출처
    "inv_perm":   "INVARIANT: auth_gate_mutable_actions",
    "inv_title":  "INVARIANT: post_title_max_length",
    "inv_page":   "INVARIANT: pagination_out_of_range_fallback",
    "inv_req":    "INVARIANT: required_field_empty_rejection",
    "inv_edit":   "INVARIANT: edit_form_validation_parity",
    "inv_hidden": "INVARIANT: non_owner_action_button_hidden",
    "inv_anon":   "INVARIANT: anonymous_write_blocked",
}


def _infer_negative_category(technique: str, scenario: str, precondition: str) -> str | None:
    """D49 — negative_* 기법에 자동 카테고리 부여 (Mock 전용 휴리스틱).

    실제 LLM은 prompt 강제로 직접 출력. Mock은 시나리오 문자열에서 키워드 추론.
    """
    if not technique.startswith("negative_"):
        return None
    text = (scenario + " " + precondition).lower()
    # 우선순위가 있는 분류
    if any(k in text for k in ("sql", "xss", "injection", "path traversal", "csrf")):
        return "injection_or_security"
    if any(k in text for k in ("중복", "이미 사용", "이미 존재", "동시", "충돌")):
        return "duplicate_or_conflict"
    if any(k in text for k in ("비로그인", "권한", "차단", "리다이렉트", "접근 불가",
                                "권한 없", "만료", "퇴장")):
        return "permission_denied"
    if any(k in text for k in ("초과", "이상", "이하", "최대", "최소", "상한", "0자", "음수")):
        return "boundary_violation"
    # 기본값: 형식·필수·빈값 등 일반 validation
    return "validation_failure"


def _t(
    tc_id, scenario, precondition, expected, technique, source_quote_key,
    confidence=0.88, applied_invariant=None, related_defect_id=None,
):
    sq = _Q.get(source_quote_key, f"INFERRED: {scenario[:40]}")
    return {
        "tc_id": tc_id,
        "scenario": scenario,
        "precondition": precondition,
        "expected": expected,
        "design_technique": technique,
        "negative_category": _infer_negative_category(technique, scenario, precondition),
        "source_quote": sq,
        "gen_confidence": confidence,
        "applied_invariant": applied_invariant,
        "related_defect_id": related_defect_id,
    }


_GNUBOARD5_TCS: dict[str, list[dict]] = {

    # ── 1.1 회원가입 ──────────────────────────────────────────────────────
    "1.1 회원가입": [
        _t("", "유효한 정보로 회원가입 성공",
           "비로그인 상태 / 회원가입 페이지(/bbs/register.php) 접속",
           "가입 완료 메시지 표시 후 로그인 페이지로 이동",
           "happy_path", "join"),
        _t("", "중복 아이디로 가입 시 오류",
           "비로그인 / 이미 존재하는 아이디 'testuser' 입력",
           "'이미 사용 중인 아이디입니다' 오류 메시지 표시, 가입 불가",
           "negative_basic", "dup_id"),
        _t("", "비밀번호 5자(미달) 입력 시 오류",
           "비로그인 / 비밀번호 필드에 'abc12' (5자) 입력",
           "'비밀번호는 6자 이상이어야 합니다' 오류 메시지 표시",
           "boundary", "pw_len"),
        _t("", "이메일 형식 오류 시 가입 거부",
           "비로그인 / 이메일 필드에 'notanemail' 입력",
           "이메일 형식 오류 메시지 표시, 가입 불가",
           "negative_basic", "email"),
        _t("", "약관 미동의 시 가입 불가",
           "비로그인 / 모든 정보 입력 후 약관 체크박스 미선택",
           "약관 동의 요구 메시지 표시, 가입 불가",
           "negative_basic", "agree"),
    ],

    # ── 1.2 로그인 / 로그아웃 ────────────────────────────────────────────
    "1.2 로그인 / 로그아웃": [
        _t("", "유효한 계정으로 로그인 성공",
           "비로그인 / 로그인 페이지(/bbs/login.php) 접속",
           "로그인 성공 후 이전 페이지(또는 메인)로 이동, 상단에 닉네임 표시",
           "happy_path", "login"),
        _t("", "틀린 비밀번호로 로그인 시 오류",
           "비로그인 / 존재하는 아이디에 잘못된 비밀번호 입력",
           "'아이디 또는 비밀번호가 올바르지 않습니다' 메시지 표시",
           "negative_basic", "fail"),
        _t("", "존재하지 않는 아이디로 로그인",
           "비로그인 / 아이디 'no_such_user', 임의 비밀번호 입력",
           "로그인 오류 메시지 표시",
           "negative_basic", "fail"),
        _t("", "로그아웃 후 회원 전용 페이지 접근 시 리다이렉트",
           "로그인 상태에서 로그아웃 클릭 / 이후 글쓰기 페이지 직접 URL 접근",
           "로그인 페이지로 리다이렉트",
           "state_transition", "noauth"),
    ],

    # ── 1.3 정보 수정 ─────────────────────────────────────────────────────
    "1.3 정보 수정": [
        _t("", "비밀번호 변경 성공",
           "로그인 상태 / 정보수정 페이지 접속 / 현재 비밀번호 입력 후 신규 비밀번호 입력",
           "비밀번호 변경 완료 메시지 표시",
           "happy_path", "join"),
        _t("", "현재 비밀번호 불일치 시 수정 거부",
           "로그인 상태 / 틀린 현재 비밀번호 입력",
           "'현재 비밀번호가 일치하지 않습니다' 오류 메시지",
           "negative_basic", "pw_len"),
        _t("", "닉네임 1자(미달) 입력 시 거부",
           "로그인 / 닉네임 필드에 '가' (1자) 입력",
           "닉네임 최소 길이 오류 메시지 표시",
           "boundary", "nick"),
    ],

    # ── 1.4 비밀번호 찾기 ────────────────────────────────────────────────
    "1.4 비밀번호 찾기": [
        _t("", "등록된 이메일로 임시 비밀번호 발송",
           "비로그인 / 비밀번호 찾기 페이지 / 가입 시 등록한 이메일 입력",
           "'임시 비밀번호를 발송했습니다' 메시지 표시",
           "happy_path", "join"),
        _t("", "미등록 이메일 입력 시 오류",
           "비로그인 / 존재하지 않는 이메일 입력",
           "'등록되지 않은 이메일입니다' 오류 메시지",
           "negative_basic", "email"),
    ],

    # ── 2.1 게시글 목록 조회 ──────────────────────────────────────────────
    "2.1 게시글 목록 조회": [
        _t("", "게시판 글 목록 정상 조회",
           "비로그인 / 게시판 URL 접속",
           "글 목록 표시, 번호·제목·작성자·날짜·조회수 열 존재",
           "happy_path", "page"),
        _t("", "페이지 2 이동 시 다음 목록 표시",
           "비로그인 / 게시판 글 20개 이상 등록된 상태 / 2페이지 클릭",
           "2번째 페이지 글 목록 표시, 1페이지와 다른 글 목록",
           "equivalence", "page"),
        _t("", "공지글이 목록 상단에 고정 표시",
           "관리자가 공지글 등록한 상태 / 일반 회원으로 목록 조회",
           "공지글이 목록 최상단에 고정 표시, 일반 글과 구분",
           "equivalence", "page"),
        _t("", "마지막 페이지 초과 번호 접근 시 처리",
           "전체 3페이지인 게시판에서 page=9999 파라미터로 접근",
           "빈 목록 또는 마지막 페이지 표시 (오류 없이 처리)",
           "boundary", "page"),
    ],

    # ── 2.2 게시글 작성 ───────────────────────────────────────────────────
    "2.2 게시글 작성": [
        _t("", "로그인 사용자의 정상 게시글 작성",
           "로그인 상태 / 게시판 글쓰기 페이지 접속 / 제목·내용 입력 후 등록",
           "글 등록 완료, 목록 또는 상세 페이지로 이동, 등록한 글 목록에 표시",
           "happy_path", "write"),
        _t("", "비로그인 상태에서 글쓰기 시도",
           "비로그인 / 글쓰기 페이지 URL 직접 접근",
           "로그인 페이지로 리다이렉트",
           "negative_basic", "noauth"),
        _t("", "제목 미입력 시 등록 거부",
           "로그인 / 글쓰기 페이지 / 제목 빈 상태로 등록 버튼 클릭",
           "'제목을 입력해주세요' 오류 메시지, 등록 불가",
           "negative_basic", "title"),
        _t("", "허용 확장자 외 파일 첨부 시 거부",
           "로그인 / 파일 첨부 필드에 .exe 파일 선택",
           "허용되지 않는 파일 형식 오류 메시지, 첨부 불가",
           "negative_basic", "file"),
    ],

    # ── 2.3 게시글 상세 조회 ──────────────────────────────────────────────
    "2.3 게시글 상세 조회": [
        _t("", "게시글 상세 정상 조회",
           "비로그인 / 게시판 목록에서 글 제목 클릭",
           "제목·내용·작성자·작성일·조회수 표시, 이전/다음 글 링크 존재",
           "happy_path", "page"),
        _t("", "조회수 중복 카운트 방지",
           "동일 IP에서 동일 글을 10초 내 2회 접근",
           "조회수 1만 증가 (중복 카운트 없음)",
           "equivalence", "page", 0.75),
        _t("", "비밀글을 비작성자가 조회 시 내용 비공개",
           "비밀글 작성자가 아닌 로그인 사용자가 비밀글 클릭",
           "'비밀글입니다' 메시지 표시, 내용 비공개",
           "negative_basic", "secret"),
    ],

    # ── 2.4 게시글 수정 ───────────────────────────────────────────────────
    "2.4 게시글 수정": [
        _t("", "작성자 본인이 게시글 수정",
           "로그인 (작성자) / 자신이 쓴 글 상세 페이지 / 수정 버튼 클릭 / 내용 변경 후 저장",
           "수정 완료, 상세 페이지에 변경된 내용 표시",
           "happy_path", "perm"),
        _t("", "타인 게시글 수정 시도 시 거부",
           "로그인 (작성자 아닌 일반 회원) / 타인의 글 수정 URL 직접 접근",
           "'수정 권한이 없습니다' 오류 메시지 또는 권한 없음 페이지",
           "negative_basic", "perm"),
        _t("", "수정 후 제목 빈칸으로 저장 시 거부",
           "로그인 (작성자) / 수정 페이지에서 제목 삭제 후 저장 클릭",
           "제목 필수 오류 메시지, 저장 불가",
           "negative_basic", "title"),
    ],

    # ── 2.5 게시글 삭제 ───────────────────────────────────────────────────
    "2.5 게시글 삭제": [
        _t("", "작성자 본인이 게시글 삭제",
           "로그인 (작성자) / 자신의 글 상세 페이지 / 삭제 버튼 클릭 / 확인 다이얼로그에서 '확인'",
           "글 삭제 완료, 게시판 목록으로 이동, 삭제된 글 목록에 미표시",
           "happy_path", "del"),
        _t("", "삭제 확인 다이얼로그에서 '취소' 선택",
           "로그인 (작성자) / 삭제 버튼 클릭 / 다이얼로그에서 '취소'",
           "삭제 취소, 상세 페이지 그대로 유지",
           "state_transition", "del"),
        _t("", "타인 게시글 삭제 시도",
           "로그인 (작성자 아닌 회원) / 타인의 글 삭제 URL 직접 접근",
           "삭제 거부 메시지 또는 권한 없음 페이지",
           "negative_basic", "perm"),
    ],

    # ── 2.6 댓글 ──────────────────────────────────────────────────────────
    "2.6 댓글": [
        _t("", "로그인 사용자의 정상 댓글 작성",
           "로그인 / 게시글 상세 / 댓글 내용 입력 후 등록",
           "댓글 목록에 내 댓글 표시, 작성자명·내용 정확",
           "happy_path", "cmnt"),
        _t("", "빈 내용으로 댓글 등록 시 거부",
           "로그인 / 댓글 내용 빈 상태로 등록 버튼 클릭",
           "내용 필수 오류 메시지, 등록 불가",
           "negative_basic", "cmnt"),
        _t("", "비로그인 시 댓글 작성 불가",
           "비로그인 / 게시글 상세 / 댓글 등록 시도",
           "로그인 요구 메시지 또는 로그인 페이지로 이동",
           "negative_basic", "noauth"),
        _t("", "댓글 작성자만 삭제 가능",
           "로그인 (댓글 작성자 아닌 회원) / 타인 댓글 삭제 URL 직접 접근",
           "삭제 거부, '권한 없음' 메시지",
           "negative_basic", "perm"),
        _t("", "대댓글(답글) 작성",
           "로그인 / 댓글의 '답글' 버튼 클릭 / 내용 입력 후 등록",
           "대댓글이 원 댓글 아래 들여쓰기로 표시",
           "equivalence", "cmnt"),
    ],

    # ── 2.7 파일 첨부 및 다운로드 ────────────────────────────────────────
    "2.7 파일 첨부 및 다운로드": [
        _t("", "허용 확장자 파일 첨부 및 다운로드",
           "로그인 / 게시글에 .pdf 파일 첨부 후 등록 / 상세에서 다운로드 클릭",
           "파일 다운로드 성공",
           "happy_path", "file"),
        _t("", "금지 확장자 파일 첨부 시 거부",
           "로그인 / .exe 파일 첨부 시도",
           "허용되지 않는 확장자 오류 메시지, 첨부 불가",
           "negative_basic", "file"),
        _t("", "용량 초과 파일 첨부 시 거부",
           "로그인 / 관리자 설정 최대 용량 초과 파일 첨부",
           "파일 용량 초과 오류 메시지",
           "boundary", "file"),
    ],

    # ── 3.1 통합 검색 ─────────────────────────────────────────────────────
    "3.1 통합 검색": [
        _t("", "제목으로 게시글 검색",
           "비로그인 / 검색창에 존재하는 게시글 제목의 일부 입력",
           "해당 키워드가 포함된 게시글 목록 표시",
           "happy_path", "search"),
        _t("", "존재하지 않는 키워드 검색",
           "비로그인 / 검색창에 '없는키워드xyz999' 입력",
           "'검색 결과가 없습니다' 메시지 또는 빈 목록 표시",
           "negative_basic", "search"),
        _t("", "내용으로 검색 시 결과 반환",
           "비로그인 / 검색 유형 '내용' 선택 후 키워드 입력",
           "본문에 해당 키워드가 포함된 게시글 목록 표시",
           "equivalence", "search"),
        _t("", "작성자명으로 검색",
           "비로그인 / 검색 유형 '작성자' 선택 후 닉네임 입력",
           "해당 닉네임의 작성자가 쓴 글 목록 표시",
           "equivalence", "search"),
    ],

    # ── 4.1 포인트 적립 및 사용 ──────────────────────────────────────────
    "4.1 포인트 적립 및 사용": [
        _t("", "게시글 작성 후 포인트 적립 확인",
           "로그인 / 포인트 지급 설정된 게시판에 글 작성",
           "마이페이지 포인트 내역에 적립 기록 표시",
           "happy_path", "point"),
        _t("", "파일 다운로드 시 포인트 차감",
           "로그인 (포인트 보유) / 다운로드 포인트 설정된 파일 다운로드",
           "포인트 차감, 내역에 차감 기록 표시",
           "equivalence", "point"),
        _t("", "포인트 부족 시 다운로드 제한",
           "로그인 (포인트 0) / 다운로드 포인트 설정된 파일 다운로드 시도",
           "'포인트가 부족합니다' 메시지, 다운로드 불가",
           "negative_basic", "point"),
    ],

    # ── 5.1 기본 환경 설정 ────────────────────────────────────────────────
    "5.1 기본 환경 설정": [
        _t("", "관리자가 사이트 제목 변경",
           "관리자 로그인 / 기본환경설정 / 사이트 제목 변경 후 저장",
           "변경된 제목이 브라우저 탭 및 헤더에 반영",
           "happy_path", "login", 0.82),
        _t("", "일반 회원이 관리자 페이지 접근 시 거부",
           "일반 회원 로그인 / /adm/ URL 직접 접근",
           "접근 불가 메시지 또는 메인 페이지로 리다이렉트",
           "negative_basic", "noauth"),
    ],

    # ── 6.1 레벨 기반 권한 ───────────────────────────────────────────────
    "6.1 레벨 기반 권한": [
        _t("", "레벨 1 회원이 레벨 2 이상 게시판 접근 시 거부",
           "레벨 1 회원 로그인 / 최소 레벨 2인 게시판 접근",
           "접근 거부 메시지 표시",
           "negative_basic", "level"),
        _t("", "레벨 조건 충족 시 게시판 접근 허용",
           "레벨 5 회원 로그인 / 최소 레벨 3인 게시판 접근",
           "게시판 목록 정상 표시",
           "equivalence", "level"),
    ],

    # ── 6.3 IP 차단 ──────────────────────────────────────────────────────
    "6.3 IP 차단": [
        _t("", "차단된 IP 접속 시 접근 불가 메시지",
           "관리자가 특정 IP 차단 설정 / 해당 IP에서 접속",
           "'접근이 제한된 IP입니다' 메시지 표시, 페이지 이용 불가",
           "happy_path", "ip"),
        _t("", "미차단 IP는 정상 접속 가능",
           "차단 목록에 없는 IP로 접속",
           "정상 페이지 표시",
           "equivalence", "ip"),
    ],

    # ── 8.1 입력 길이 제한 ───────────────────────────────────────────────
    "8.1 입력 길이 제한": [
        _t("", "아이디 2자(최소 미달) 가입 시 거부",
           "비로그인 / 가입 페이지 / 아이디 'ab' (2자) 입력",
           "아이디 최소 길이(3자) 오류 메시지",
           "boundary", "id_len"),
        _t("", "아이디 21자(최대 초과) 가입 시 거부",
           "비로그인 / 가입 페이지 / 아이디 21자 입력",
           "아이디 최대 길이(20자) 오류 메시지",
           "boundary", "id_len"),
        _t("", "게시글 제목 255자 입력 성공, 256자 시도 시 처리",
           "로그인 / 글쓰기 / 제목 256자 입력",
           "255자로 자동 잘리거나 오류 메시지 표시",
           "boundary", "title"),
    ],

    # ── 5.2 회원 관리 (관리자) ───────────────────────────────────────────
    "5.2 회원 관리": [
        _t("", "관리자가 회원 레벨 변경", "관리자 로그인 / 회원관리 / 특정 회원 레벨 5로 변경 후 저장",
           "변경된 레벨 저장, 해당 회원 레벨 5인 게시판 접근 가능", "happy_path", "level"),
        _t("", "관리자가 특정 회원 강제 탈퇴", "관리자 로그인 / 회원관리 / 대상 회원 선택 후 탈퇴 처리",
           "해당 아이디로 로그인 불가", "equivalence", "level"),
        _t("", "일반 회원이 관리자 회원관리 페이지 접근 거부", "일반 회원 로그인 / /adm/member_list.php 직접 접근",
           "접근 거부 메시지 또는 리다이렉트", "negative_basic", "noauth"),
    ],
    # ── 5.3 게시판 관리 ──────────────────────────────────────────────────
    "5.3 게시판 관리": [
        _t("", "관리자가 새 게시판 그룹 생성", "관리자 로그인 / 게시판관리 / 그룹 추가",
           "새 그룹이 목록에 표시", "happy_path", "level"),
        _t("", "게시판 접근 최소 레벨 설정 후 하위 레벨 회원 접근 거부",
           "관리자가 게시판 최소 레벨을 5로 설정 / 레벨 3 회원 접근",
           "접근 거부 메시지 표시", "equivalence", "level"),
        _t("", "게시판 삭제 시 내부 글도 함께 삭제",
           "관리자 로그인 / 기존 글 존재하는 게시판 삭제",
           "게시판 및 하위 글 삭제, 해당 게시판 URL 접근 시 오류",
           "equivalence", "del"),
    ],
    # ── 5.4 게시글 관리 (관리자) ─────────────────────────────────────────
    "5.4 게시글 관리": [
        _t("", "관리자가 타인 게시글 강제 삭제", "관리자 로그인 / 임의 게시글 / 삭제 버튼",
           "게시글 삭제, 목록에서 제거", "happy_path", "perm"),
        _t("", "관리자가 게시글 다른 게시판으로 이동",
           "관리자 / 게시글 선택 / 이동 기능으로 다른 게시판 지정",
           "원 게시판에서 제거, 대상 게시판에 표시", "equivalence", "perm"),
    ],
    # ── 5.5 메뉴 관리 ────────────────────────────────────────────────────
    "5.5 메뉴 관리": [
        _t("", "관리자가 메뉴 항목 추가", "관리자 / 메뉴관리 / 새 항목 이름·URL 입력 후 저장",
           "메인 메뉴에 새 항목 표시", "happy_path", "level"),
        _t("", "메뉴 순서 변경", "관리자 / 메뉴관리 / 드래그 또는 순서 변경 후 저장",
           "변경된 순서로 메뉴 표시", "equivalence", "level"),
    ],
    # ── 6.2 비밀글 ───────────────────────────────────────────────────────
    "6.2 비밀글": [
        _t("", "비밀글 작성 후 작성자 본인 조회", "로그인 / 비밀글 옵션 체크 후 게시글 작성 / 상세 조회",
           "내용 정상 표시", "happy_path", "secret"),
        _t("", "비밀글을 비작성자가 조회 시 내용 숨김",
           "로그인 (비작성자) / 비밀글 제목 클릭",
           "'비밀글입니다' 또는 비밀번호 입력 요구, 내용 미표시", "negative_basic", "secret"),
        _t("", "관리자는 비밀글 내용 조회 가능",
           "관리자 로그인 / 일반 회원이 작성한 비밀글 클릭",
           "내용 정상 표시", "equivalence", "secret"),
    ],
    # ── 7.1 상품 관리 (영카트) ───────────────────────────────────────────
    "7.1 상품 관리": [
        _t("", "관리자가 상품 등록", "관리자 / 영카트 상품관리 / 이름·가격·재고 입력 후 등록",
           "상품 목록에 새 상품 표시", "happy_path", "login", 0.75),
        _t("", "비로그인 상태에서 장바구니 담기 시 로그인 요구",
           "비로그인 / 상품 상세 / 장바구니 버튼 클릭",
           "로그인 요구 메시지 또는 로그인 페이지 이동", "negative_basic", "noauth", 0.75),
    ],
    # ── 7.2 주문 및 결제 ─────────────────────────────────────────────────
    "7.2 주문 및 결제": [
        _t("", "장바구니 상품 수량 변경", "로그인 / 장바구니 / 수량 2로 변경",
           "합계 금액 자동 재계산", "happy_path", "login", 0.72),
        _t("", "장바구니에서 상품 삭제", "로그인 / 장바구니 / 상품 삭제 버튼",
           "해당 상품 장바구니에서 제거, 합계 재계산", "equivalence", "del", 0.72),
        _t("", "주문 시 재고 0인 상품 주문 불가",
           "로그인 / 재고 0 상품 주문 시도",
           "'품절' 또는 '재고 없음' 메시지, 주문 불가", "negative_basic", "login", 0.70),
    ],
    # ── 8.2 파일 업로드 제한 ─────────────────────────────────────────────
    "8.2 파일 업로드 제한": [
        _t("", "허용 확장자 외 파일 거부", "로그인 / 게시글 첨부 / .exe 파일 선택",
           "허용되지 않는 확장자 오류 메시지", "negative_basic", "file"),
        _t("", "파일 용량 초과 시 오류", "로그인 / 관리자 설정 최대 용량보다 큰 파일 첨부",
           "파일 용량 초과 오류 메시지, 첨부 불가", "boundary", "file"),
        _t("", "용량 이내 파일 정상 업로드", "로그인 / 허용 확장자·용량 이내 파일 첨부",
           "파일 첨부 성공, 상세 페이지에 다운로드 링크 표시", "happy_path", "file"),
    ],
    # ── 8.3 중복 처리 ────────────────────────────────────────────────────
    "8.3 중복 처리": [
        _t("", "중복 아이디 가입 거부", "비로그인 / 이미 존재하는 아이디로 가입 시도",
           "'이미 사용 중인 아이디' 오류", "negative_basic", "dup_id"),
        _t("", "단시간 도배 게시글 제한",
           "로그인 / 동일 게시판에 30초 이내 5개 글 작성 시도",
           "도배 방지 메시지 또는 작성 제한", "boundary", "write", 0.70),
        _t("", "중복 이메일 가입 경고",
           "비로그인 / 이미 가입된 이메일로 회원가입 시도",
           "이메일 중복 경고 메시지 표시", "equivalence", "email", 0.75),
    ],
}


def _generic_tcs(leaf: str, mid: str, major: str, excerpt: str) -> list[dict]:
    """미리 정의되지 않은 leaf에 대한 기본 TC 3개 생성."""
    src = f"MANUAL: {excerpt[:60]}" if excerpt else f"INFERRED: {leaf} 기본 동작"
    return [
        {
            "tc_id": "",
            "scenario": f"{leaf} 정상 동작 확인",
            "precondition": f"로그인 상태 / {major} > {mid} > {leaf} 화면 접속",
            "expected": f"{leaf} 기능이 정상적으로 동작하고 성공 메시지 또는 결과 표시",
            "design_technique": "happy_path",
            "source_quote": src,
            "gen_confidence": 0.70,
            "applied_invariant": None,
            "related_defect_id": None,
        },
        {
            "tc_id": "",
            "scenario": f"{leaf} 비로그인 접근 시 거부",
            "precondition": f"비로그인 상태 / {leaf} URL 직접 접근",
            "expected": "로그인 페이지로 리다이렉트",
            "design_technique": "negative_basic",
            "source_quote": "MANUAL: 비로그인 상태에서 회원 전용 기능 접근 시 로그인 페이지로 이동",
            "gen_confidence": 0.72,
            "applied_invariant": None,
            "related_defect_id": None,
        },
        {
            "tc_id": "",
            "scenario": f"{leaf} 필수 입력 누락 시 오류",
            "precondition": f"로그인 상태 / {leaf} 화면 / 필수 입력 비워둔 채 제출",
            "expected": "필수 입력 항목 오류 메시지 표시, 제출 불가",
            "design_technique": "negative_basic",
            "source_quote": "INVARIANT: required_field_empty_rejection",
            "gen_confidence": 0.68,
            "applied_invariant": "required_field_empty_rejection",
            "related_defect_id": "DEF-2026-BRD-004",
        },
    ]
