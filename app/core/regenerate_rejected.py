"""거부된 TC를 reviewer_note 기반으로 재생성.

- Reviewer Gate에서 사용자가 'rejected' + 사유를 입력한 TC들이 대상
- leaf별로 그룹화 → 각 leaf의 거부 사유를 LLM에 전달 → TC_DESIGN 재호출
- 결과로 거부된 TC를 교체 (승인/수정 TC는 보존)
"""
from __future__ import annotations
from typing import Callable

from app.assets.invariants_loader import load_invariants_multi, format_for_llm as fmt_invariants
from app.assets.defect_catalog import search_similar_defects, format_for_llm as fmt_defects
from app.assets.product_types import classify_product_types
from app.validation.v10_negative_coverage import applicable_categories_for_leaf
from app.core.stage2_tc_design import (
    _format_negative_categories, _guess_feature_type,
)


def regenerate_rejected(
    tcs: list[dict],
    llm_client,
    manual_text: str = "",
    progress_cb: Callable[[str], None] | None = None,
) -> tuple[list[dict], int, int]:
    """rejected TC를 reviewer_note 기반으로 재생성.

    Returns:
        (새 tcs 리스트, 교체된 TC 수, 실패한 leaf 수)
    """
    def _cb(msg: str) -> None:
        if progress_cb:
            progress_cb(msg)

    # 1) rejected TC를 leaf별로 그룹화 (소분류 + requirement_id 키)
    rejected_groups: dict[tuple, list[dict]] = {}
    for tc in tcs:
        if (tc.get("review_status") or "").lower() == "rejected":
            key = (tc.get("소분류", ""), tc.get("requirement_id", ""))
            rejected_groups.setdefault(key, []).append(tc)

    if not rejected_groups:
        _cb("재생성 대상 없음 — 거부된 TC가 0개입니다.")
        return list(tcs), 0, 0

    _cb(f"재생성 시작 — {sum(len(v) for v in rejected_groups.values())}개 거부 TC, "
        f"{len(rejected_groups)}개 leaf 그룹")

    # 2) 자산 준비 (한 번만)
    product_type_ids = classify_product_types(manual_text or "")
    invariants = load_invariants_multi(product_type_ids)

    replaced_count = 0
    failed_leaf_count = 0

    # 3) leaf별로 TC_DESIGN 재호출 후 거부된 TC 교체
    new_tcs: list[dict] = list(tcs)   # 원본 보존, 인덱스로 교체

    for (leaf_name, req_id), rejected_list in rejected_groups.items():
        sample = rejected_list[0]
        # 거부 사유 종합
        notes = []
        for r in rejected_list:
            note = (r.get("reviewer_note") or "").strip()
            tc_id = r.get("tc_id", "?")
            tech = r.get("design_technique", "")
            scenario = (r.get("scenario") or "")[:120]
            notes.append(
                f"- [{tc_id}] ({tech}) {scenario}\n"
                f"    거부 사유: {note or '(미입력)'}"
            )
        combined_notes = "\n".join(notes)

        # 입력 구성
        category_major = sample.get("대분류", "")
        category_mid   = sample.get("중분류", "")
        feature_type   = _guess_feature_type(leaf_name)
        invariants_text = fmt_invariants(invariants, feature_type=feature_type)
        similar_defects = search_similar_defects(product_type_ids, feature_type, top_k=3)
        defects_text = fmt_defects(similar_defects)

        # 거부 사유를 manual_excerpt 앞에 prepend — 별도 contract 없이 컨텍스트 전달
        excerpt_prefix = (
            f"[중요] 이전에 다음 TC들이 사용자에 의해 거부되었습니다.\n"
            f"거부 사유를 반드시 반영해 동일한 실수를 반복하지 마세요.\n\n"
            f"{combined_notes}\n\n"
            f"---\n\n"
        )
        manual_excerpt = (excerpt_prefix + (manual_text or "(매뉴얼 미첨부)"))[:1500]

        # tc_id_start — 충돌 방지를 위해 큰 번호로 시작 (R 접두사로 구분)
        # 기존 TC-XXX-001 형식 유지하되 003->101 식으로 오프셋
        leaf_num = "RGN"
        tc_id_start = f"TC-{leaf_num}-001"

        _cb(f"   leaf '{leaf_name}' 재생성 중 ({len(rejected_list)}개 TC 교체 시도)")
        try:
            result = llm_client.call("TC_DESIGN", {
                "category_major":   category_major,
                "category_mid":     category_mid,
                "category_leaf":    leaf_name,
                "requirement_id":   req_id,
                "tc_id_start":      tc_id_start,
                "manual_excerpt":   manual_excerpt,
                "domain_invariants": invariants_text or "(없음)",
                "similar_past_defects": defects_text or "(없음)",
                "negative_categories": _format_negative_categories(leaf_name),
            })
        except Exception as e:
            err_msg = str(e).splitlines()[0][:200]
            _cb(f"⚠ leaf '{leaf_name}' 재생성 실패: {err_msg}")
            failed_leaf_count += 1
            continue

        new_generated = result.get("tcs", []) or []
        if not new_generated:
            _cb(f"⚠ leaf '{leaf_name}' 재생성 — LLM이 빈 결과 반환")
            failed_leaf_count += 1
            continue

        # 거부된 TC 인덱스를 찾아 새 TC로 교체
        # 한 leaf의 거부 TC가 N개고 새 TC가 M개일 때:
        #   M <= N: 앞쪽 N개를 새 M개로 교체, 나머지 N-M개는 제거
        #   M >  N: 앞쪽 N개를 새 N개로 교체, 추가 M-N개는 append
        rejected_indices: list[int] = []
        for i, tc in enumerate(new_tcs):
            if (tc.get("소분류", "") == leaf_name
                    and tc.get("requirement_id", "") == req_id
                    and (tc.get("review_status") or "").lower() == "rejected"):
                rejected_indices.append(i)

        # 새 TC 정규화 (stage2와 동일한 후처리)
        normalized_new: list[dict] = []
        for j, tc in enumerate(new_generated, 1):
            if "expected_output" in tc and "expected" not in tc:
                tc["expected"] = tc.pop("expected_output")
            if "technique" in tc and "design_technique" not in tc:
                tc["design_technique"] = tc.pop("technique")
            # 원본 TC ID 형식 유지 — 첫 거부 TC의 ID 패턴 따름
            # (간단하게는 사용자 식별을 위해 [재생성] 마커는 reviewer_note에 기록)
            base_id = rejected_list[min(j-1, len(rejected_list)-1)].get("tc_id", "")
            if base_id:
                tc["tc_id"] = f"{base_id}-R"   # 재생성 표시
            else:
                tc["tc_id"] = f"TC-RGN-{j:03d}"
            tc["대분류"] = category_major
            tc["중분류"] = category_mid
            tc["소분류"] = leaf_name
            tc["requirement_id"] = req_id
            tc["screenshot_file"] = sample.get("screenshot_file", "")
            # G4 — 재생성된 TC는 pending 상태로 되돌림 (재검토 필요)
            tc["review_status"] = "pending"
            tc["reviewer_note"] = (
                "🔄 재생성됨 — 이전 거부 사유 반영. 재검토 필요."
            )
            tc["reviewer_id"]   = ""
            # G5 초기화
            tc.setdefault("actual", "")
            tc.setdefault("result", "not_executed")
            tc.setdefault("failure_reason", "")
            tc.setdefault("exec_confidence", 0.0)
            tc.setdefault("failure_category", "")
            tc.setdefault("failure_category_source", "")
            # G6 negative_category
            if (tc.get("design_technique", "") or "").startswith("negative_"):
                tc.setdefault("negative_category", "")
            else:
                tc.setdefault("negative_category", None)
            normalized_new.append(tc)

        # 교체 로직
        n_old, n_new = len(rejected_indices), len(normalized_new)
        for i, new_tc in enumerate(normalized_new[:n_old]):
            new_tcs[rejected_indices[i]] = new_tc
        replaced_count += min(n_old, n_new)

        # 남은 새 TC가 있으면 마지막 거부 위치 뒤에 삽입
        if n_new > n_old:
            insert_pos = rejected_indices[-1] + 1 if rejected_indices else len(new_tcs)
            for k, extra in enumerate(normalized_new[n_old:]):
                new_tcs.insert(insert_pos + k, extra)
            replaced_count += (n_new - n_old)

        # 남은 거부 TC가 있으면 (n_old > n_new) 제거 — 뒤에서부터
        elif n_new < n_old:
            for idx in sorted(rejected_indices[n_new:], reverse=True):
                del new_tcs[idx]

    _cb(
        f"재생성 완료 — TC {replaced_count}개 교체/생성, "
        f"실패 leaf {failed_leaf_count}개"
    )
    return new_tcs, replaced_count, failed_leaf_count
