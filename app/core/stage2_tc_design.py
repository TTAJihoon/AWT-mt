"""Stage 2 — leaf별 TC 설계 (LLM TC_DESIGN v2.1 호출).

v2.1 변경 (D49): negative_categories 입력 추가 — leaf 유형별 음성 카테고리 강제.
"""
from __future__ import annotations
import concurrent.futures as _cf
from collections import OrderedDict
from typing import Callable

from app.core.stage1_ingest import excerpt_for_leaf
from app.assets.invariants_loader import load_invariants_multi, format_for_llm as fmt_invariants
from app.assets.defect_catalog import search_similar_defects, format_for_llm as fmt_defects
from app.assets.product_types import classify_product_types
from app.validation.v10_negative_coverage import applicable_categories_for_leaf


# D49 — LLM 프롬프트용 카테고리 짧은 설명
_CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "validation_failure":    "입력 형식·필수값 위반 (이메일 형식, 빈 필드, 길이 미달)",
    "duplicate_or_conflict": "중복·동시성·충돌 (중복 아이디, 동시 수정, 이미 존재하는 키)",
    "permission_denied":     "권한 거부 (비로그인, 권한 없는 사용자, 만료 토큰)",
    "boundary_violation":    "경계값 초과 (최대 길이 +1, 0/음수, 파일 크기 상한 초과)",
    "injection_or_security": "보안 공격 패턴 (SQL injection, XSS, Path traversal, CSRF)",
}


def _format_negative_categories(leaf_name: str) -> str:
    """leaf에 적용되는 negative 카테고리를 LLM 입력용 텍스트로 포맷."""
    cats = applicable_categories_for_leaf(leaf_name)
    if not cats:
        return "(이 leaf는 음성 카테고리 강제 대상이 아닙니다 — negative_category=null 허용)"
    lines = [f"이 leaf에서 강제 적용해야 하는 음성 카테고리 (각 ≥ 1 TC):"]
    for c in cats:
        lines.append(f"- {c}: {_CATEGORY_DESCRIPTIONS[c]}")
    return "\n".join(lines)

# featureType 추정 (leaf category → featureType 매핑)
_FEATURE_TYPE_MAP: dict[str, str] = {
    "등록": "CREATE", "작성": "CREATE", "추가": "CREATE", "생성": "CREATE",
    "수정": "UPDATE", "편집": "UPDATE", "변경": "UPDATE",
    "삭제": "DELETE", "제거": "DELETE",
    "조회": "READ", "목록": "READ", "검색": "SEARCH", "페이지": "PAGINATION",
    "로그인": "AUTH", "로그아웃": "AUTH", "인증": "AUTH", "권한": "PERMISSION",
}


def _guess_feature_type(leaf_name: str) -> str:
    for keyword, ftype in _FEATURE_TYPE_MAP.items():
        if keyword in leaf_name:
            return ftype
    return "OTHER"


_CONFIDENCE_ORDER = {"HIGH": 0, "MID": 1, "INFERRED": 2, "": 3}

# D54 — 그룹(페이지)당 한 번에 설계할 leaf 최대 수 (토큰 예산 보호)
_GROUP_CAP = 12
# D54-B — 교차 페이지 시나리오 TC 상한 + 도메인당 요약 기능명 수
_MAX_FLOWS = 15
_FLOW_NAMES_PER_DOMAIN = 15


def _build_site_summary(leaves: list[dict], names_per_domain: int = _FLOW_NAMES_PER_DOMAIN) -> str:
    """도메인(대분류)별 기능명 요약 — 교차 플로우 설계 입력(이름만, 분량 작게)."""
    dom: "OrderedDict[str, list[str]]" = OrderedDict()
    for lf in leaves:
        maj = lf.get("category_major", "") or "기타"
        nm = f"{lf.get('category_mid','')}>{lf.get('category_leaf','')}".strip(">")
        if not nm:
            continue
        dom.setdefault(maj, [])
        if nm not in dom[maj]:
            dom[maj].append(nm)
    lines = []
    for maj, names in dom.items():
        shown = names[:names_per_domain]
        extra = f" 외 {len(names) - len(shown)}개" if len(names) > len(shown) else ""
        lines.append(f"[{maj}] " + ", ".join(shown) + extra)
    return "\n".join(lines)


def _design_cross_flows(leaves: list[dict], llm_client, _cb) -> list[dict]:
    """D54-B — 사이트 전체 요약으로 교차 페이지 사용자 여정 TC 설계."""
    if not leaves:
        return []
    summary = _build_site_summary(leaves)
    _cb(f"교차 페이지 시나리오 설계 (최대 {_MAX_FLOWS}개)…")
    try:
        result = llm_client.call("TC_FLOW", {
            "site_summary": summary,
            "max_journeys": str(_MAX_FLOWS),
        })
    except Exception as e:
        _cb(f"⚠ 교차 플로우 설계 실패(건너뜀): {str(e).splitlines()[0][:150]}")
        return []

    flows = result.get("flows") or result.get("tcs") or []
    out: list[dict] = []
    for i, fl in enumerate(flows[:_MAX_FLOWS], 1):
        steps = fl.get("steps", "")
        if isinstance(steps, list):
            steps = "\n".join(
                s if str(s).strip().startswith(tuple("0123456789"))
                else f"{j}. {s}"
                for j, s in enumerate(steps, 1)
            )
        scenario = (fl.get("scenario", "") or fl.get("title", "")).strip()
        if steps:
            scenario = (scenario + "\n" + str(steps)).strip()
        involved = fl.get("involved_features", [])
        if isinstance(involved, list):
            involved = ", ".join(str(x) for x in involved)
        out.append({
            "tc_id":           f"TC-FLOW-{i:03d}",
            "대분류":          "교차 시나리오",
            "중분류":          "사용자 여정",
            "소분류":          fl.get("title", "") or f"여정 {i}",
            "requirement_id":  f"FLOW-{i:03d}",
            "scenario":        scenario,
            "precondition":    fl.get("precondition", ""),
            "expected":        fl.get("expected_output", "") or fl.get("expected", ""),
            "design_technique": "cross_feature",
            "negative_category": None,
            "source_quote":    (f"INFERRED: 교차 페이지 여정 (연계 기능: {involved})"
                                 if involved else "INFERRED: 교차 페이지 여정"),
            "gen_confidence":  fl.get("gen_confidence", 0.5),
            "applied_invariant": None,
            "related_defect_id": None,
            "screenshot_file": "",
            "review_status": "pending", "reviewer_note": "", "reviewer_id": "",
            "actual": "", "result": "not_executed", "failure_reason": "",
            "exec_confidence": 0.0, "failure_category": "", "failure_category_source": "",
        })
    _cb(f"교차 페이지 시나리오 TC {len(out)}개 생성")
    return out


def _prioritize_leaves(leaves: list[dict], max_leaves: int) -> list[dict]:
    """신뢰도(HIGH→MID→INFERRED) 우선 정렬 후 max_leaves 개수로 자름.
    max_leaves=0이면 자르지 않음.
    """
    if max_leaves <= 0 or len(leaves) <= max_leaves:
        return leaves
    sorted_leaves = sorted(
        leaves,
        key=lambda lf: _CONFIDENCE_ORDER.get(
            str(lf.get("confidence", "")).upper(), 3
        ),
    )
    return sorted_leaves[:max_leaves]


def design(
    leaves: list[dict],
    manual_text: str,
    llm_client,
    defect_patterns: str = "",  # 하위 호환 (사용 안 함, 자산에서 로드)
    max_leaves: int = 0,        # 0 = 무제한; >0이면 신뢰도 우선으로 상위 N개만 처리
    progress_cb: Callable[[str], None] | None = None,
    failed_leaves_out: list[dict] | None = None,    # 추적성용: 실패한 leaf 정보 기록처
    excluded_leaves_out: list[dict] | None = None,  # 추적성용: max_leaves cap으로 제외된 leaf
    should_stop: Callable[[], bool] | None = None,  # 사용자 중단 신호 (협력적)
    concurrency: int = 1,                            # 동시 그룹 호출 수 (D55)
) -> list[dict]:
    """모든 leaf에 대해 TC를 생성해 단일 리스트로 반환.

    Args:
        failed_leaves_out:   리스트 전달 시 분석 실패한 leaf의 {idx, name, reason}을 append.
        excluded_leaves_out: 리스트 전달 시 max_leaves cap으로 잘린 leaf의 {idx, name, confidence}을 append.
    """
    def _cb(msg: str):
        if progress_cb:
            progress_cb(msg)

    # max_leaves 적용 (API 비용·무료 쿼터 보호)
    original_count = len(leaves)

    # ── 안전 가드 (C): max_leaves=0(무제한)인데 leaves가 너무 많으면 자동 제한 ──
    SAFETY_CAP = 100
    leaves_before_cap = list(leaves)   # 추적성: 제외된 leaf 식별용 원본 보관

    if max_leaves <= 0 and original_count > SAFETY_CAP:
        leaves = _prioritize_leaves(leaves, SAFETY_CAP)
        _cb(
            f"⚠ leaf {original_count}개 → 안전 제한 {SAFETY_CAP}개 자동 적용 "
            f"(max_leaves=0). 무제한 실행이 필요하면 max_leaves를 명시적 큰 값(예: 9999)으로 설정하세요."
        )
    elif max_leaves > 0:
        leaves = _prioritize_leaves(leaves, max_leaves)
        if original_count > max_leaves:
            _cb(
                f"TC 설계 대상 leaf {original_count}개 → 상위 {len(leaves)}개로 제한 "
                f"(max_leaves={max_leaves}; 해제하려면 설정에서 0으로 변경)"
            )

    # 추적성: max_leaves cap으로 제외된 leaf 목록 기록
    if excluded_leaves_out is not None and len(leaves) < len(leaves_before_cap):
        included_names = {lf.get("category_leaf") for lf in leaves}
        for i, lf in enumerate(leaves_before_cap, 1):
            if lf.get("category_leaf") not in included_names:
                excluded_leaves_out.append({
                    "idx":        i,
                    "name":       lf.get("category_leaf", ""),
                    "confidence": str(lf.get("confidence", "")),
                    "source_url": lf.get("source_url", ""),
                })

    # 제품 유형 분류 (전체 매뉴얼 기준)
    product_type_ids = classify_product_types(manual_text)
    invariants = load_invariants_multi(product_type_ids)

    all_tcs: list[dict] = []
    failed_leaves: list[tuple[int, str, str]] = []   # (leaf_num, leaf명, 오류요약)

    # ── D54: 페이지(source_url) 단위 그룹핑 + cap 서브배치 ──────────────────
    # leaf 1개씩이 아니라 같은 화면 기능을 묶어 TC_DESIGN_GROUP 1회 호출 →
    # LLM이 기능 관계를 보고(중복↓·cross_feature↑) 호출 수도 급감.
    indexed = list(enumerate(leaves, 1))            # (leaf_num, leaf) — tc_id용 안정 번호
    groups: "OrderedDict[str, list]" = OrderedDict()
    for leaf_num, leaf in indexed:
        url = leaf.get("source_url") or "(미상)"
        groups.setdefault(url, []).append((leaf_num, leaf))
    batches: list[tuple[str, list]] = []
    for url, members in groups.items():
        for i in range(0, len(members), _GROUP_CAP):
            batches.append((url, members[i:i + _GROUP_CAP]))

    _cb(f"TC 설계 — 기능 {len(leaves)}개를 {len(batches)}개 그룹(페이지 단위)으로 설계")

    def _finalize(tc: dict, leaf: dict, leaf_num: int, seq_map: dict) -> dict:
        """LLM 출력 TC를 내부 스키마로 정규화 + 소속 leaf 필드 부여.
        seq_map은 배치-로컬(각 leaf는 한 배치에만 속하므로 동시성 안전)."""
        if "expected_output" in tc and "expected" not in tc:
            tc["expected"] = tc.pop("expected_output")
        if "technique" in tc and "design_technique" not in tc:
            tc["design_technique"] = tc.pop("technique")
        tc.pop("leaf_index", None)
        seq = seq_map.get(leaf_num, 0) + 1
        seq_map[leaf_num] = seq
        tc["tc_id"]           = f"TC-{leaf_num:03d}-{seq:03d}"
        tc["대분류"]          = leaf.get("category_major", "")
        tc["중분류"]          = leaf.get("category_mid", "")
        tc["소분류"]          = leaf.get("category_leaf", "")
        tc["requirement_id"]  = leaf.get("requirement_id", "")
        tc["screenshot_file"] = leaf.get("screenshot_file", "")   # Stage 0 스크린샷 연결
        tc.setdefault("review_status", "pending")
        tc.setdefault("reviewer_note", "")
        tc.setdefault("reviewer_id", "")
        tc.setdefault("actual", "")
        tc.setdefault("result", "not_executed")
        tc.setdefault("failure_reason", "")
        tc.setdefault("exec_confidence", 0.0)
        tc.setdefault("failure_category", "")
        tc.setdefault("failure_category_source", "")
        if (tc.get("design_technique", "") or "").startswith("negative_"):
            tc.setdefault("negative_category", "")
        else:
            tc.setdefault("negative_category", None)
        return tc

    def _process_batch(b_idx: int, url: str, members: list) -> dict:
        """한 그룹(페이지)을 설계 → {tcs, failed, quota}. 스레드에서 실행 가능."""
        ftypes: list[str] = []
        for _, leaf in members:
            ft = _guess_feature_type(leaf.get("category_leaf", ""))
            if ft not in ftypes:
                ftypes.append(ft)
        inv_parts, def_parts = [], []
        for ft in ftypes:
            t = fmt_invariants(invariants, feature_type=ft)
            if t and t not in inv_parts:
                inv_parts.append(t)
            dt = fmt_defects(search_similar_defects(product_type_ids, ft, top_k=2))
            if dt and dt not in def_parts:
                def_parts.append(dt)
        lines = []
        for gi, (leaf_num, leaf) in enumerate(members, 1):
            excerpt = excerpt_for_leaf(manual_text, leaf)[:400]
            negcats = _format_negative_categories(leaf.get("category_leaf", ""))
            lines.append(
                f"{gi}. [{leaf.get('category_major','')} > {leaf.get('category_mid','')} > "
                f"{leaf.get('category_leaf','')}] (req={leaf.get('requirement_id','')})\n"
                f"   명세: {excerpt or '(없음)'}\n"
                f"   {negcats}"
            )
        _cb(f"TC 설계 중 (그룹 {b_idx}/{len(batches)}): {url} — 기능 {len(members)}개")

        try:
            result = llm_client.call("TC_DESIGN_GROUP", {
                "page_context":         f"{url}  (기능 {len(members)}개)",
                "features_block":       "\n".join(lines),
                "domain_invariants":    "\n".join(inv_parts) or "(없음)",
                "similar_past_defects": "\n".join(def_parts) or "(없음)",
            })
        except Exception as e:
            err_msg = str(e).splitlines()[0][:200]
            failed = [{"idx": ln, "name": lf.get("category_leaf", ""), "reason": err_msg}
                      for ln, lf in members]
            _cb(f"⚠ 그룹 분석 실패 ({b_idx}/{len(batches)}): {url} — {err_msg}")
            return {"tcs": [], "failed": failed,
                    "quota": ("일일 쿼터" in err_msg or "PerDay" in err_msg)}

        seq_map: dict[int, int] = {}
        out = []
        for tc in result.get("tcs", []):
            try:
                gi = int(tc.get("leaf_index", 1))
            except (TypeError, ValueError):
                gi = 1
            if gi < 1 or gi > len(members):
                gi = 1
            leaf_num, leaf = members[gi - 1]
            out.append(_finalize(tc, leaf, leaf_num, seq_map))
        return {"tcs": out, "failed": [], "quota": False}

    # ── D55: 그룹 단위 병렬/순차 실행 (입력 순서로 병합 → 결정성 유지) ──────
    def _merge(res: dict):
        all_tcs.extend(res["tcs"])
        for f in res["failed"]:
            failed_leaves.append((f["idx"], f["name"], f["reason"]))
            if failed_leaves_out is not None:
                failed_leaves_out.append(f)

    if concurrency <= 1 or len(batches) <= 1:
        for b_idx, (url, members) in enumerate(batches, 1):
            if should_stop and should_stop():
                _cb(f"⏹ 사용자 중단 — TC 설계 종료 ({b_idx-1}/{len(batches)} 그룹)")
                break
            res = _process_batch(b_idx, url, members)
            _merge(res)
            if res["quota"]:
                _cb(f"⚠ 일일 쿼터 초과로 Stage 2 조기 종료 — TC {len(all_tcs)}개")
                break
    else:
        with _cf.ThreadPoolExecutor(max_workers=concurrency) as ex:
            futs = {
                ex.submit(_process_batch, b_idx, url, members): b_idx
                for b_idx, (url, members) in enumerate(batches, 1)
            }
            results: dict[int, dict] = {}
            for fut in _cf.as_completed(futs):
                if should_stop and should_stop():
                    for f in futs:
                        f.cancel()
                    break
                results[futs[fut]] = fut.result()
            # 입력(그룹) 순서로 병합 — tc_id·출력 재현성 보장
            for b_idx in sorted(results):
                _merge(results[b_idx])

    # ── D54-B: 교차 페이지 시나리오(cross_feature) 패스 ─────────────────────
    if leaves and not (should_stop and should_stop()):
        all_tcs.extend(_design_cross_flows(leaves, llm_client, _cb))

    if failed_leaves:
        _cb(
            f"Stage 2 완료 - TC {len(all_tcs)}개 생성 "
            f"(분석 실패 leaf {len(failed_leaves)}개)"
        )
    else:
        _cb(f"Stage 2 완료 - TC {len(all_tcs)}개 생성")
    return all_tcs
