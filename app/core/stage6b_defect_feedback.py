"""Stage 6B — real_defect TC를 결함 카탈로그에 자동 피드백 (Feature D).

Stage 6 완료 후 호출.
failure_category == 'real_defect'인 TC에서 결함 JSON + patternProposal을 자동 생성해
data/assets/defect-catalog/ 에 저장한다.

검수자 승인 전까지:
  defect.status = "OPEN"
  patternProposal.status = "candidate"
"""
from __future__ import annotations
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TYPE_CHECKING

from app.assets.defect_catalog import next_defect_id, save_defect, list_defects

if TYPE_CHECKING:
    from app.api.llm_client import LLMClient
    from app.auth.db_client import DBClient

# ── 추론 테이블 ───────────────────────────────────────────────────────────────

_FEATURE_TYPE_KEYWORDS: list[tuple[list[str], str]] = [
    (["로그인", "인증", "로그아웃", "세션", "비밀번호", "가입", "회원", "탈퇴"], "AUTH"),
    (["작성", "등록", "업로드", "첨부", "글쓰기", "생성", "추가"], "CREATE"),
    (["수정", "편집", "변경", "업데이트"], "UPDATE"),
    (["삭제", "제거"], "DELETE"),
    (["조회", "목록", "뷰", "보기", "읽기", "상세"], "READ"),
    (["검색", "필터", "정렬"], "SEARCH"),
    (["페이지", "페이징", "번호", "next", "prev", "이전", "다음"], "PAGINATION"),
    (["권한", "허가", "접근", "제어", "소유", "관리자"], "PERMISSION"),
]

_TECHNIQUE_SEVERITY: dict[str, str] = {
    "negative_deep":    "CRITICAL",
    "negative_basic":   "MAJOR",
    "happy_path":       "BLOCKER",
    "boundary":         "MAJOR",
    "equivalence":      "MAJOR",
    "state_transition": "MAJOR",
}

_ISO_MAPPING: dict[str, tuple[str, str]] = {
    "AUTH":       ("보안성",        "진정성"),
    "PERMISSION": ("보안성",        "접근 제어성"),
    "CREATE":     ("기능 적합성",   "기능 정확성"),
    "UPDATE":     ("기능 적합성",   "기능 정확성"),
    "DELETE":     ("기능 적합성",   "기능 완전성"),
    "READ":       ("기능 적합성",   "기능 완전성"),
    "SEARCH":     ("기능 적합성",   "기능 정확성"),
    "PAGINATION": ("신뢰성",        "결함 허용성"),
    "OTHER":      ("기능 적합성",   "기능 완전성"),
}

_ROOT_CAUSE_CATEGORY: dict[str, str] = {
    "AUTH":       "BACKEND",
    "PERMISSION": "BACKEND",
    "CREATE":     "BACKEND",
    "UPDATE":     "FRONTEND",
    "DELETE":     "BACKEND",
    "READ":       "FRONTEND",
    "SEARCH":     "BACKEND",
    "PAGINATION": "FRONTEND",
    "OTHER":      "BACKEND",
}

_DEFECT_CATEGORY: dict[str, str] = {
    "AUTH":       "AUTH_BYPASS",
    "PERMISSION": "AUTH_BYPASS",
    "CREATE":     "INPUT_VALIDATION",
    "UPDATE":     "UI_CONSISTENCY",
    "DELETE":     "BUSINESS_RULE",
    "READ":       "BUSINESS_RULE",
    "SEARCH":     "BUSINESS_RULE",
    "PAGINATION": "BOUNDARY",
    "OTHER":      "OTHER",
}


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _infer_feature_type(tc: dict) -> str:
    text = " ".join([
        tc.get("소분류", ""),
        tc.get("scenario", ""),
        tc.get("precondition", ""),
    ]).lower()
    for keywords, ftype in _FEATURE_TYPE_KEYWORDS:
        if any(kw in text for kw in keywords):
            return ftype
    return "OTHER"


def _build_defect_from_tc(
    tc: dict,
    defect_id: str,
    product_type_id: str,
    run_id: str,
    actor_username: str,
) -> dict:
    feature_type = _infer_feature_type(tc)
    technique     = tc.get("design_technique", "negative_basic")
    severity      = _TECHNIQUE_SEVERITY.get(technique, "MAJOR")
    iso_char, iso_sub = _ISO_MAPPING.get(feature_type, ("기능 적합성", "기능 완전성"))
    root_cat      = _ROOT_CAUSE_CATEGORY.get(feature_type, "BACKEND")
    defect_cat    = _DEFECT_CATEGORY.get(feature_type, "OTHER")

    raw_title = tc.get("scenario", "알 수 없는 시나리오")
    title = (raw_title[:47] + "...") if len(raw_title) > 50 else raw_title

    failure_reason = tc.get("failure_reason", "")
    desc_match = re.search(r"\[원인후보\]\s*(.+?)(?:\n|$)", failure_reason)
    description = desc_match.group(1).strip() if desc_match else failure_reason[:200]

    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "defectId":   defect_id,
        "projectId":  f"RUN-{run_id}",
        "discoveredAt": now_iso,
        "product": {
            "productTypeId": product_type_id,
            "techStack": [],
            "scale": "MEDIUM",
        },
        "feature": {
            "featureType":     feature_type,
            "screenLocation":  tc.get("precondition", "")[:100],
            "triggeringAction": tc.get("scenario", "")[:100],
        },
        "title":            title,
        "description":      description or raw_title[:200],
        "observedBehavior": tc.get("actual", "")[:300],
        "expectedBehavior": tc.get("expected", "")[:300],
        "iso25023Mapping": {
            "characteristic":    iso_char,
            "subcharacteristic": iso_sub,
        },
        "severity":       severity,
        "defectCategory": defect_cat,
        "detection": {
            "method":           "AUTO_TC",
            "detectingTcId":    tc.get("tc_id"),
            "timeToDetectMin":  1,
        },
        "rootCause": {
            "category":       root_cat,
            "whatWasMissed":  description[:100],
        },
        "learning": {
            "patternProposal": None,
        },
        "tags":       [],
        "status":     "OPEN",
        "resolution": "",
        "_meta": {
            "createdBy":          actor_username,
            "createdAt":          now_iso,
            "patternGeneratedBy": "AI",
            "patternApprovedBy":  None,
            "patternApprovedAt":  None,
        },
    }


def _call_pattern_extract(llm_client: "LLMClient", defect: dict) -> dict | None:
    try:
        return llm_client.call("PATTERN_EXTRACT", {
            "defect_id":          defect["defectId"],
            "product_type_ids":   [defect["product"]["productTypeId"]],
            "feature_type":       defect["feature"]["featureType"],
            "title":              defect["title"],
            "description":        defect["description"],
            "observed_behavior":  defect["observedBehavior"],
            "expected_behavior":  defect["expectedBehavior"],
            "root_cause_category": defect["rootCause"]["category"],
        })
    except Exception:
        return None


def _append_invariant_to_yaml(product_type_id: str, invariant: dict) -> bool:
    """suggestedInvariant를 domain-invariants YAML에 candidate로 추가.

    Returns True if appended, False otherwise.
    """
    yaml_path = (
        Path(__file__).parent.parent.parent
        / "data" / "assets" / "domain-invariants"
        / f"{product_type_id}.yaml"
    )
    if not yaml_path.exists():
        return False
    try:
        import yaml
        content = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        items: list[dict] = content.get("invariants", [])
        existing_names = {i.get("name") for i in items}
        if invariant.get("name") in existing_names:
            return False
        now_iso = datetime.now(timezone.utc).isoformat()
        items.append({
            "name":         invariant["name"],
            "statement":    invariant["statement"],
            "appliesTo":    invariant.get("appliesTo", []),
            "verification": invariant.get("verification", ""),
            "status":       "candidate",
            "_addedAt":     now_iso,
            "_addedBy":     "AI",
        })
        content["invariants"] = items
        yaml_path.write_text(
            yaml.dump(content, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


# ── 공개 API ──────────────────────────────────────────────────────────────────

def feedback(
    tcs: list[dict],
    llm_client: "LLMClient",
    product_type_id: str = "BOARD_CMS",
    run_id: str = "unknown",
    actor_username: str = "awt_system",
    db: "DBClient | None" = None,
    progress_cb: Callable[[str], None] | None = None,
    min_confidence: float = 0.4,
) -> list[dict]:
    """real_defect TC → 결함 카탈로그 자동 피드백.

    Args:
        tcs:             Stage 5~6 결과 TC 목록
        llm_client:      LLM 클라이언트
        product_type_id: 결함 카탈로그 분류 (BOARD_CMS 등)
        run_id:          현재 run ID (projectId 기록용)
        actor_username:  생성자로 기록할 계정명
        db:              DB 클라이언트 (이벤트 로깅. None이면 스킵)
        progress_cb:     진행 콜백
        min_confidence:  후보 최소 exec_confidence (기본 0.4)

    Returns:
        새로 생성된 결함 dict 목록
    """
    def _cb(msg: str) -> None:
        if progress_cb:
            progress_cb(msg)

    # 1) real_defect 후보 필터링
    candidates = [
        tc for tc in tcs
        if tc.get("failure_category") == "real_defect"
        and float(tc.get("exec_confidence") or 0.0) >= min_confidence
    ]
    _cb(f"Stage 6B: real_defect 후보 {len(candidates)}건 (신뢰도 ≥ {min_confidence})")
    if not candidates:
        _cb("  결함 카탈로그 피드백 없음 (real_defect 없거나 신뢰도 미달)")
        return []

    # 2) 이미 카탈로그에 있는 TC ID 중복 제거
    existing_tc_ids: set[str] = {
        d.get("detection", {}).get("detectingTcId", "")
        for d in list_defects(product_type_id)
    }

    new_defects: list[dict] = []
    for i, tc in enumerate(candidates, 1):
        tc_id = tc.get("tc_id", "")
        if tc_id in existing_tc_ids:
            _cb(f"  [{i}/{len(candidates)}] {tc_id}: 카탈로그 중복 — 스킵")
            continue

        defect_id = next_defect_id(product_type_id)
        _cb(f"  [{i}/{len(candidates)}] {tc_id} → {defect_id} 생성")

        # 3) 결함 dict 구성
        defect = _build_defect_from_tc(tc, defect_id, product_type_id, run_id, actor_username)

        # 4) PATTERN_EXTRACT LLM 호출
        pattern_result = _call_pattern_extract(llm_client, defect)
        if pattern_result:
            proposal = pattern_result.get("patternProposal")
            if proposal:
                proposal["generatedBy"] = "AI"
                proposal["status"] = "candidate"
                defect["learning"]["patternProposal"] = proposal
                _cb(f"    패턴: {proposal.get('name', '?')}")

            inv = pattern_result.get("suggestedInvariant")
            if inv and _append_invariant_to_yaml(product_type_id, inv):
                _cb(f"    불변규칙 후보 추가: {inv.get('name', '?')}")
        else:
            _cb(f"    PATTERN_EXTRACT 실패 — patternProposal 없이 저장")

        # 5) 결함 파일 저장
        save_defect(defect, actor_username, db)
        existing_tc_ids.add(tc_id)
        new_defects.append(defect)

    total = len(new_defects)
    _cb(f"Stage 6B 완료: 결함 카탈로그 {total}건 추가" if total else "Stage 6B 완료: 신규 결함 없음")
    return new_defects
