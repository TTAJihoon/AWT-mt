"""Stage 3 — V1~V10 검증 + 실패 시 TC_REGEN 재호출 (doc/03-tc-schema.md §5).

V10 추가 (D49): negative 카테고리 커버리지 강제.

아키텍처 노트 (Bug-1 수정):
  V10 실패 tc_id = "LEAF:F001" 형식 → 실제 TC id와 매칭 안 됨.
  V10은 기존 TC를 고치는 게 아니라 누락 카테고리 TC를 *추가* 해야 하므로
  TC_REGEN 루프에서 분리, _add_v10_tcs()로 별도 처리.
"""
from __future__ import annotations
import re
from typing import Callable

from app.validation import v10_negative_coverage

_REQUIRED_COLS = [
    "tc_id", "대분류", "중분류", "소분류", "scenario",
    "precondition", "expected", "requirement_id",
    "design_technique", "source_quote", "gen_confidence",
]
_VALID_TECHNIQUES = {
    "happy_path", "equivalence", "boundary",
    "negative_basic", "negative_deep", "state_transition", "cross_feature",
}
_TC_ID_RE = re.compile(r"^TC-\d{3}-\d{3}$")

# V3 INFERRED 임계 (PoC 결과 30% 완화, 실제 OSS 10% 재강제)
INFERRED_THRESHOLD = 0.30
# V10 최소 카테고리 커버리지 (D49)
NEGATIVE_COVERAGE_MIN = 0.6


_REGEN_BATCH_SIZE = 10   # V3 REGEN: 한 번에 처리할 최대 TC 수
_REGEN_TC_JSON_LIMIT = 6000  # failed_tcs_json 문자 한계


def verify(
    tcs: list[dict],
    manual_text: str,
    llm_client,
    leaves: list[dict],
    max_retries: int = 3,
    inferred_threshold: float = INFERRED_THRESHOLD,
    progress_cb: Callable[[str], None] | None = None,
    concurrency: int = 1,
) -> list[dict]:
    """V1~V5 검증. 실패 TC는 재호출(최대 max_retries회). 최종 TC 목록 반환."""
    def _cb(msg: str):
        if progress_cb:
            progress_cb(msg)

    for attempt in range(1, max_retries + 1):
        all_failures = _check_all(tcs, manual_text, leaves, inferred_threshold)

        # V10 (카테고리 추가) vs 구조적 오류 (V1-V5, TC_REGEN 대상) 분리
        structural = [f for f in all_failures if f["v"] != "V10"]
        v10_gaps   = [f for f in all_failures if f["v"] == "V10"]

        if not structural:
            # 구조적 오류 없음 — V10 gap만 남은 경우 TC 추가 후 완료
            if v10_gaps:
                _cb(f"  V10 커버리지 부족 {len(v10_gaps)}개 leaf - 누락 카테고리 TC 추가 생성")
                new_tcs = _add_v10_tcs(v10_gaps, leaves, manual_text, tcs, llm_client, _cb, concurrency)
                tcs.extend(new_tcs)
            _cb(f"Stage 3 완료 (시도 {attempt}회) - 모든 검증 통과")
            return tcs

        # V1-V5 구조적 실패 → TC_REGEN
        _cb(f"  구조적 실패 {len(structural)}건 (시도 {attempt}/{max_retries}) - TC_REGEN 호출")
        failed_ids  = {f["tc_id"] for f in structural}

        # "ALL" 실패(V3/V4/V5)는 tc_id가 "ALL"로 기록됨 → 실제 대상 TC 선별
        has_all_failure = "ALL" in failed_ids
        failed_ids.discard("ALL")

        if has_all_failure:
            vs_all = {f["v"] for f in structural if f["tc_id"] == "ALL"}
            if "V3" in vs_all:
                # V3: INFERRED 비율 초과 → INFERRED TC만 재생성
                # gen_confidence 낮은 순(개선 여지 높은 순) 상위 REGEN_BATCH_SIZE개만 선택
                inferred_tcs = [
                    tc for tc in tcs
                    if _classify_source_quote(str(tc.get("source_quote", ""))) == "inferred"
                ]
                inferred_tcs.sort(key=lambda t: float(t.get("gen_confidence", 0.5)))
                for tc in inferred_tcs[:_REGEN_BATCH_SIZE]:
                    failed_ids.add(tc["tc_id"])
            if "V4" in vs_all:
                # V4: happy_path 비율 초과 → happy_path TC 일부 재생성
                hp_tcs = [tc for tc in tcs if tc.get("design_technique") == "happy_path"]
                for tc in hp_tcs[len(hp_tcs)//2:]:   # 후반 절반만 대상
                    failed_ids.add(tc["tc_id"])
            if "V5" in vs_all:
                # V5: leaf 미커버 → 전체 재생성 (어느 TC를 수정해야 할지 불명확)
                for tc in tcs:
                    failed_ids.add(tc["tc_id"])

        failed_tcs = [tc for tc in tcs if tc.get("tc_id") in failed_ids]

        fix_instructions = _build_fix_instructions(structural)
        # manual_excerpt: failed_tcs의 requirement_id에 해당하는 매뉴얼 발췌문
        manual_excerpt = _extract_manual_for_tcs(failed_tcs, manual_text)
        # TC_REGEN은 캐시 불사용 — 동일 입력이라도 재시도마다 새 API 호출 필요
        # (캐시 히트 시 동일 실패 결과 반복 → 재시도 무의미해짐)
        # ── 복원력 (D54 동일): TC_REGEN 실패가 Stage 3 전체를 죽이지 않게 함 ──
        # 빈 응답·일일 쿼터·안전 필터 등으로 호출이 실패하면, 지금까지 생성된 TC를
        # 보존한 채 재생성을 포기하고 우아한 degradation 경로로 넘어간다.
        try:
            regen_result = llm_client.call("TC_REGEN", {
                "manual_excerpt":   manual_excerpt[:2000],
                "failed_tcs_json":  str(failed_tcs)[:_REGEN_TC_JSON_LIMIT],
                "v_failures":       str(structural)[:800],
                "fix_instructions": fix_instructions[:400],
            }, use_cache=False)
        except Exception as e:
            err_msg = str(e).splitlines()[0][:200]
            _cb(
                f"⚠ TC 재작성 실패 (시도 {attempt}/{max_retries}) — {err_msg}\n"
                f"      지금까지 생성된 TC {len(tcs)}개를 보존하고 검증을 종료합니다"
            )
            break   # 재시도 루프 탈출 → 아래 degradation 경로(잔여 실패 INFERRED 마킹)

        # 재생성된 TC로 교체 + 필드 정규화
        regen_map = {}
        for tc in regen_result.get("tcs", []):
            # TC_REGEN 출력 필드 → 내부 스키마 정규화 (stage2와 동일)
            if "expected_output" in tc and "expected" not in tc:
                tc["expected"] = tc.pop("expected_output")
            if "technique" in tc and "design_technique" not in tc:
                tc["design_technique"] = tc.pop("technique")
            regen_map[tc["tc_id"]] = tc

        for i, tc in enumerate(tcs):
            if tc.get("tc_id") in regen_map:
                merged = {**tc, **regen_map[tc["tc_id"]]}
                # source_quote 강등 방지: MANUAL/INVARIANT → INFERRED 로의 교체 차단
                orig_sq = str(tc.get("source_quote", ""))
                new_sq  = str(merged.get("source_quote", ""))
                if (orig_sq.startswith(("MANUAL:", "INVARIANT:", "DEFECT:"))
                        and _classify_source_quote(new_sq) == "inferred"):
                    merged["source_quote"] = orig_sq  # 원본 복원
                # V1 검증: REGEN 결과가 V1 실패이면 원본 유지 (악화 방지)
                if _v1([merged]):
                    continue  # 원본 tc 유지, merged 적용 거부
                tcs[i] = merged

    # 최대 재시도 초과 — 구조적 잔여 실패만 INFERRED 마킹
    _cb("Stage 3: 최대 재시도 초과 - 구조적 잔여 실패 TC를 INFERRED 마킹")
    remaining    = _check_all(tcs, manual_text, leaves, inferred_threshold)
    str_remain   = [f for f in remaining if f["v"] != "V10"]
    v10_remain   = [f for f in remaining if f["v"] == "V10"]

    # V1 개별 실패만 INFERRED 마킹 — V2(인용 불일치)·V3(비율)·V4·V5는 MANUAL TC를 강등하지 않음
    # MANUAL/INVARIANT source_quote는 max_retry_exceeded로 절대 교체 금지
    v1_failed_ids = {f["tc_id"] for f in str_remain if f["v"] == "V1"}
    for tc in tcs:
        if tc.get("tc_id") in v1_failed_ids:
            existing_sq = str(tc.get("source_quote", ""))
            if not existing_sq.startswith(("MANUAL:", "INVARIANT:", "DEFECT:")):
                tc["source_quote"]  = "INFERRED: max_retry_exceeded"
                tc["review_status"] = "pending"

    # V10 gap이 남아 있어도 마지막으로 한 번 TC 추가 시도
    if v10_remain:
        _cb(f"  V10 gap {len(v10_remain)}개 leaf - 최후 TC 추가 시도")
        new_tcs = _add_v10_tcs(v10_remain, leaves, manual_text, tcs, llm_client, _cb, concurrency)
        tcs.extend(new_tcs)

    return tcs


def _check_all(tcs, manual_text, leaves, inferred_threshold) -> list[dict]:
    failures = []
    failures += _v1(tcs)
    failures += _v2(tcs, manual_text)
    failures += _v3(tcs, inferred_threshold)
    failures += _v4(tcs)
    failures += _v5(tcs, leaves)
    failures += _v10(tcs, leaves)
    return failures


def _add_v10_tcs(
    v10_gaps: list[dict],
    leaves: list[dict],
    manual_text: str,
    existing_tcs: list[dict],
    llm_client,
    _cb,
    concurrency: int = 1,
) -> list[dict]:
    """V10 커버리지 부족 leaf에 누락 카테고리 TC를 추가 생성.

    TC_REGEN 대신 TC_DESIGN을 재호출해 누락 카테고리만 타깃으로 새 TC를 만든다.
    기존 TC와 ID 충돌 방지를 위해 leaf별 최대 번호 + 1로 시작.
    """
    # lazy imports — stage2 유틸 재사용, 순환 의존 방지
    import concurrent.futures as _cf
    from collections import OrderedDict
    from app.core.stage1_ingest import excerpt_for_leaf
    from app.assets.invariants_loader import load_invariants_multi, format_for_llm as fmt_inv
    from app.assets.defect_catalog import search_similar_defects, format_for_llm as fmt_def
    from app.assets.product_types import classify_product_types
    from app.core.stage2_tc_design import (
        _CATEGORY_DESCRIPTIONS, _guess_feature_type, _GROUP_CAP,
    )

    _V10_CAP_PER_LEAF = 6   # D56 — leaf당 V10 보완 TC 상한(과증식 억제)

    leaf_by_rid = {lf["requirement_id"]: lf for lf in leaves}
    leaf_to_idx = {lf["requirement_id"]: i + 1 for i, lf in enumerate(leaves)}

    # 기존 TC ID 최대 번호 (leaf별)
    existing_max: dict[str, int] = {}
    for tc in existing_tcs:
        rid = tc.get("requirement_id", "")
        m = re.match(r"TC-\d{3}-(\d{3})$", tc.get("tc_id", ""))
        if m and rid:
            existing_max[rid] = max(existing_max.get(rid, 0), int(m.group(1)))

    # 제품 유형·불변 규칙 (공통)
    product_type_ids = classify_product_types(manual_text)
    inv_map = load_invariants_multi(product_type_ids)

    # ── D56: gap leaf를 source_url(페이지)+cap로 그룹핑 → 그룹당 1회 호출 ──────
    items = []   # (leaf_num, rid, leaf, missing)
    for gap in v10_gaps:
        rid     = gap.get("leaf_rid", "")
        missing = gap.get("missing_categories", [])
        leaf    = leaf_by_rid.get(rid)
        if not leaf or not missing:
            continue
        items.append((leaf_to_idx.get(rid, 1), rid, leaf, missing))

    groups: "OrderedDict[str, list]" = OrderedDict()
    for it in items:
        url = it[2].get("source_url") or "(미상)"
        groups.setdefault(url, []).append(it)
    batches: list[list] = []
    for url, members in groups.items():
        for i in range(0, len(members), _GROUP_CAP):
            batches.append(members[i:i + _GROUP_CAP])

    def _process_v10_batch(b_idx: int, members: list) -> list[dict]:
        """한 그룹의 V10 보완 TC 생성 → 리스트 반환. 스레드에서 실행 가능.
        각 rid(leaf)는 한 배치에만 속하므로 tc_id 번호는 배치-로컬로 안전."""
        ftypes: list[str] = []
        for _, _, leaf, _ in members:
            ft = _guess_feature_type(leaf.get("category_leaf", ""))
            if ft not in ftypes:
                ftypes.append(ft)
        inv_parts, def_parts = [], []
        for ft in ftypes:
            t = fmt_inv(inv_map, feature_type=ft)
            if t and t not in inv_parts:
                inv_parts.append(t)
            dt = fmt_def(search_similar_defects(product_type_ids, ft, top_k=2))
            if dt and dt not in def_parts:
                def_parts.append(dt)
        lines = []
        for gi, (leaf_num, rid, leaf, missing) in enumerate(members, 1):
            excerpt = excerpt_for_leaf(manual_text, leaf)[:300]
            missing_desc = "; ".join(
                f"{c}({_CATEGORY_DESCRIPTIONS.get(c, '')})" for c in missing
            )
            lines.append(
                f"{gi}. [{leaf.get('category_major','')} > {leaf.get('category_mid','')} > "
                f"{leaf.get('category_leaf','')}]\n"
                f"   명세: {excerpt or '(없음)'}\n"
                f"   누락 음성 카테고리(각 ≥1 TC): {missing_desc}"
            )
        _cb(f"  V10 보완 (그룹 {b_idx}/{len(batches)}): {len(members)}개 기능")
        try:
            result = llm_client.call("TC_V10_GROUP", {
                "features_block":       "\n".join(lines),
                "domain_invariants":    "\n".join(inv_parts) or "(없음)",
                "similar_past_defects": "\n".join(def_parts) or "(없음)",
            })
        except Exception as e:
            _cb(f"  ⚠ V10 보완 그룹 실패(건너뜀): {str(e).splitlines()[0][:150]}")
            return []

        out: list[dict] = []
        per_leaf_added: dict[str, int] = {}
        local_seq: dict[str, int] = {}
        for tc in result.get("tcs", []):
            try:
                gi = int(tc.get("leaf_index", 1))
            except (TypeError, ValueError):
                gi = 1
            if gi < 1 or gi > len(members):
                gi = 1
            leaf_num, rid, leaf, missing = members[gi - 1]
            if per_leaf_added.get(rid, 0) >= _V10_CAP_PER_LEAF:
                continue   # 증식 상한

            if "expected_output" in tc and "expected" not in tc:
                tc["expected"] = tc.pop("expected_output")
            if "technique" in tc and "design_technique" not in tc:
                tc["design_technique"] = tc.pop("technique")
            tc.pop("leaf_index", None)
            local_seq[rid] = local_seq.get(rid, 0) + 1
            next_num = existing_max.get(rid, 0) + local_seq[rid]   # 초기 base + 배치 로컬 증가
            tc["tc_id"]           = f"TC-{leaf_num:03d}-{next_num:03d}"
            tc["대분류"]          = leaf["category_major"]
            tc["중분류"]          = leaf["category_mid"]
            tc["소분류"]          = leaf["category_leaf"]
            tc["requirement_id"]  = rid
            tc["screenshot_file"] = leaf.get("screenshot_file", "")   # D58 — 스크린샷 전파
            tc.setdefault("review_status", "pending")
            tc.setdefault("reviewer_note", "")
            tc.setdefault("reviewer_id",  "")
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
            out.append(tc)
            per_leaf_added[rid] = per_leaf_added.get(rid, 0) + 1
        return out

    # ── D55: V10 보완 그룹 병렬/순차 실행 (입력 순서로 병합) ──────────────────
    new_tcs: list[dict] = []
    if concurrency <= 1 or len(batches) <= 1:
        for b_idx, members in enumerate(batches, 1):
            new_tcs.extend(_process_v10_batch(b_idx, members))
    else:
        with _cf.ThreadPoolExecutor(max_workers=concurrency) as ex:
            futs = {ex.submit(_process_v10_batch, b_idx, members): b_idx
                    for b_idx, members in enumerate(batches, 1)}
            results: dict[int, list] = {}
            for fut in _cf.as_completed(futs):
                results[futs[fut]] = fut.result()
            for b_idx in sorted(results):
                new_tcs.extend(results[b_idx])

    return new_tcs


def _v10(tcs: list[dict], leaves: list[dict]) -> list[dict]:
    """V10 — D49 negative_category 커버리지 강제."""
    return v10_negative_coverage.verify(
        tcs, leaves, min_coverage=NEGATIVE_COVERAGE_MIN,
    )


def _v1(tcs: list[dict]) -> list[dict]:
    failures = []
    for tc in tcs:
        missing = [c for c in _REQUIRED_COLS if not str(tc.get(c, "")).strip()]
        if missing or not _TC_ID_RE.match(str(tc.get("tc_id", ""))):
            failures.append({"tc_id": tc.get("tc_id", "?"), "v": "V1",
                              "reason": f"필수 컬럼 비어있거나 tc_id 형식 오류: {missing}"})
    return failures


def _classify_source_quote(sq: str) -> str:
    """source_quote를 3단계로 분류: 'manual' | 'invariants' | 'inferred'"""
    if sq.startswith("INFERRED"):
        return "inferred"
    if sq.startswith("INVARIANT:") or sq.startswith("DEFECT:"):
        return "invariants"
    return "manual"


def _v2(tcs: list[dict], manual_text: str) -> list[dict]:
    """V2: MANUAL 출처는 매뉴얼 대조, INVARIANT/INFERRED는 skip."""
    failures = []
    normalized = re.sub(r"\s+", " ", manual_text)
    for tc in tcs:
        sq = str(tc.get("source_quote", ""))
        source_type = _classify_source_quote(sq)
        if source_type != "manual":
            continue  # INVARIANT·INFERRED는 V2 대조 대상 아님
        # MANUAL: 접두어 제거 후 대조
        quote = sq.removeprefix("MANUAL:").strip()[:80]
        if len(quote) > 10:
            norm_q = re.sub(r"\s+", " ", quote)
            if norm_q not in normalized:
                failures.append({"tc_id": tc.get("tc_id"), "v": "V2",
                                  "reason": f"source_quote 매뉴얼 불일치: '{quote[:40]}'"})
    return failures


def _v3(tcs: list[dict], threshold: float) -> list[dict]:
    """V3: INFERRED(추론) 비율만 임계 적용. INVARIANT 출처는 신뢰 소스로 분리."""
    if not tcs:
        return []
    inferred_cnt = sum(
        1 for tc in tcs if _classify_source_quote(str(tc.get("source_quote", ""))) == "inferred"
    )
    ratio = inferred_cnt / len(tcs)
    if ratio > threshold:
        return [{"tc_id": "ALL", "v": "V3",
                 "reason": f"INFERRED 비율 {ratio:.1%} > 임계 {threshold:.1%} "
                            f"(INVARIANT 출처는 제외)"}]
    return []


def _v4(tcs: list[dict]) -> list[dict]:
    if not tcs:
        return []
    happy_cnt = sum(1 for tc in tcs if tc.get("design_technique") == "happy_path")
    ratio = happy_cnt / len(tcs)
    if ratio > 0.50:
        return [{"tc_id": "ALL", "v": "V4",
                 "reason": f"happy_path 비율 {ratio:.1%} > 50%"}]
    return []


def _v5(tcs: list[dict], leaves: list[dict]) -> list[dict]:
    covered = {tc.get("requirement_id") for tc in tcs}
    missing = [lf["requirement_id"] for lf in leaves if lf["requirement_id"] not in covered]
    if missing:
        return [{"tc_id": "ALL", "v": "V5",
                 "reason": f"leaf 미커버: {missing}"}]
    return []


def _extract_manual_for_tcs(failed_tcs: list[dict], manual_text: str) -> str:
    """failed_tcs의 소분류(category_leaf) 또는 시나리오 키워드로 매뉴얼 발췌.

    TC가 참조하는 기능명을 키워드로 삼아 매뉴얼에서 관련 단락을 추출한다.
    - 각 TC의 소분류·시나리오에서 첫 단어(핵심 명사) 추출
    - 매뉴얼에서 해당 단어가 포함된 줄 ± 2줄 추출
    - 중복 제거 후 반환
    """
    keywords: set[str] = set()
    for tc in failed_tcs:
        for field in ("소분류", "scenario", "precondition"):
            val = str(tc.get(field, ""))
            # 첫 4 음절어 이상 단어 추출 (공백 분리)
            for word in val.split():
                word = word.strip(".,()[]「」『』")
                if len(word) >= 4:
                    keywords.add(word)
                    if len(keywords) >= 10:
                        break
            if len(keywords) >= 10:
                break

    if not keywords:
        # 키워드 없으면 매뉴얼 앞부분 반환
        return manual_text[:1500]

    lines = manual_text.splitlines()
    hit_lines: list[int] = []
    for i, line in enumerate(lines):
        if any(kw in line for kw in keywords):
            hit_lines.extend(range(max(0, i - 2), min(len(lines), i + 3)))

    if not hit_lines:
        return manual_text[:1500]

    seen: set[int] = set()
    excerpts: list[str] = []
    for idx in sorted(set(hit_lines)):
        if idx not in seen:
            excerpts.append(lines[idx])
            seen.add(idx)

    return "\n".join(excerpts)


def _build_fix_instructions(failures: list[dict]) -> str:
    vs = {f["v"] for f in failures}
    parts = []
    if "V1" in vs:
        parts.append("필수 컬럼을 모두 채우고 tc_id는 TC-XXX-YYY 형식으로 수정하세요.")
    if "V2" in vs:
        parts.append("source_quote는 매뉴얼 원문을 직접 인용하거나 'INFERRED: 근거'로 표기하세요.")
    if "V3" in vs:
        parts.append("INFERRED 비율을 줄이도록 매뉴얼 근거를 더 많이 활용하세요.")
    if "V4" in vs:
        parts.append("happy_path 외 다른 기법(boundary, negative_deep 등)을 더 사용하세요.")
    if "V5" in vs:
        parts.append("모든 leaf 기능에 최소 1개 TC를 포함하세요.")
    if "V10" in vs:
        parts.append(
            "각 leaf의 적용 가능 negative 카테고리(validation_failure/duplicate_or_conflict/"
            "permission_denied/boundary_violation/injection_or_security) 중 누락된 카테고리에 "
            "negative_basic 또는 negative_deep TC를 1개씩 추가하세요."
        )
    return " / ".join(parts)
