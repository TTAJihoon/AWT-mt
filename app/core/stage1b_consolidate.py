"""Stage 1b — LLM 기능 통합 (의미 기준 중복 병합).

DOM 스캔은 전역 컴포넌트(헤더/푸터/로그인폼/검색창)를 페이지마다 재추출하므로
같은 기능이 다른 이름·분류로 수백 개 중복된다. 규칙 기반 정규화로는 표현 차이를
못 잡으므로, LLM(FEATURE_CONSOLIDATE)으로 의미 기준 병합한다.

전략 (배치 + 2단계):
  1. leaf를 배치(기본 250개)로 나눠 각 배치를 LLM이 병합 → 배치 내 대표 목록
  2. 배치 대표들을 다시 모아 최종 병합 (배치 간 중복 제거)
  병합되며 멤버의 출처/스크린샷은 대표 leaf에 누적.
"""
from __future__ import annotations
from typing import Callable

_BATCH_SIZE = 250          # 배치당 기능 수 (이름만이라 비교적 큼)
_MIN_TO_CONSOLIDATE = 60   # 이 수 이하면 통합 생략 (이미 적음)


def consolidate(
    leaves: list[dict],
    llm_client,
    progress_cb: Callable[[str], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> tuple[list[dict], dict]:
    """leaf 목록을 의미 기준으로 병합. (consolidated_leaves, report) 반환.

    실패·중단 시 원본 leaves를 그대로 반환(안전).
    """
    def _cb(msg: str) -> None:
        if progress_cb:
            progress_cb(msg)

    n0 = len(leaves)
    if n0 <= _MIN_TO_CONSOLIDATE:
        return leaves, {"before": n0, "after": n0, "skipped": True}

    _cb(f"기능 통합 시작 — {n0}개를 의미 기준으로 병합합니다 (LLM)")

    # ── 정렬-배치 (아이디어 2) ───────────────────────────────────────────────
    # 입력 순서대로 배치하면 같은 종류(예: 메뉴 링크)가 여러 배치로 흩어져
    # LLM이 한 배치 안에서 못 만나 병합되지 않는다. (대분류,중분류,소분류) 기준으로
    # 정렬해 동종 기능이 같은 배치에 모이게 하면 실제 병합률이 오른다.
    # 정렬은 결정적(determinism) → 재현성 유지.
    def _sort_key(lf: dict) -> tuple:
        return (
            (lf.get("category_major", "") or "").strip().lower(),
            (lf.get("category_mid", "") or "").strip().lower(),
            (lf.get("category_leaf", "") or "").strip().lower(),
        )
    sorted_leaves = sorted(leaves, key=_sort_key)

    # ── 1단계: 배치별 병합 ────────────────────────────────────────────────
    batches = [sorted_leaves[i:i + _BATCH_SIZE] for i in range(0, n0, _BATCH_SIZE)]
    stage1_reps: list[dict] = []
    failed_batches = 0
    for bi, batch in enumerate(batches, 1):
        if should_stop and should_stop():
            _cb("⏹ 사용자 중단 — 기능 통합 중단 (원본 유지)")
            return leaves, {"before": n0, "after": n0, "stopped": True}
        _cb(f"   기능 통합 중 (배치 {bi}/{len(batches)}, {len(batch)}개)")
        merged = _consolidate_batch(batch, llm_client)
        if merged is None:
            failed_batches += 1
            # 실패 배치는 원본 그대로 대표로 편입 (손실 방지)
            stage1_reps.extend(batch)
        else:
            stage1_reps.extend(merged)

    _cb(f"   1단계 완료 — {n0}개 → {len(stage1_reps)}개 (배치 실패 {failed_batches})")

    # ── 2단계: 배치 대표들 재병합 (배치 간 중복 제거) ─────────────────────
    final = stage1_reps
    if len(stage1_reps) > _BATCH_SIZE:
        # 대표가 여전히 많으면 한 번 더 (배치로) — 보통 1~2배치
        _cb(f"   2단계 — 배치 간 중복 재병합 ({len(stage1_reps)}개)")
        merged2: list[dict] = []
        for i in range(0, len(stage1_reps), _BATCH_SIZE):
            if should_stop and should_stop():
                break
            chunk = stage1_reps[i:i + _BATCH_SIZE]
            m = _consolidate_batch(chunk, llm_client)
            merged2.extend(m if m is not None else chunk)
        final = merged2
    elif len(stage1_reps) > _MIN_TO_CONSOLIDATE:
        if not (should_stop and should_stop()):
            m = _consolidate_batch(stage1_reps, llm_client)
            if m is not None:
                final = m

    # requirement_id 재부여
    for i, lf in enumerate(final, 1):
        lf["requirement_id"] = f"F{i:03d}"

    report = {
        "before":         n0,
        "after":          len(final),
        "failed_batches": failed_batches,
        "skipped":        False,
    }
    _cb(f"✅ 기능 통합 완료 — {n0}개 → 고유 {len(final)}개")
    return final, report


def _consolidate_batch(batch: list[dict], llm_client) -> list[dict] | None:
    """배치 1개를 LLM으로 병합. 실패 시 None."""
    # 입력 목록 구성 (번호. [대분류 > 중분류] 기능명)
    lines = []
    for i, lf in enumerate(batch):
        maj = lf.get("category_major", "") or "-"
        mid = lf.get("category_mid", "") or "-"
        leaf = lf.get("category_leaf", "") or "-"
        lines.append(f"{i}. [{maj} > {mid}] {leaf}")
    feature_list = "\n".join(lines)

    try:
        result = llm_client.call("FEATURE_CONSOLIDATE", {
            "feature_list": feature_list,
        }, use_cache=True)
    except Exception:
        return None

    groups = result.get("groups", [])
    if not groups:
        return None

    consolidated: list[dict] = []
    assigned: set[int] = set()
    for g in groups:
        members = [m for m in g.get("members", []) if isinstance(m, int) and 0 <= m < len(batch)]
        if not members:
            continue
        rep_src = batch[members[0]]   # 첫 멤버를 대표 베이스로 (스크린샷 등 승계)
        merged_sources: list[str] = []
        for mi in members:
            assigned.add(mi)
            src = batch[mi].get("source_url", "")
            if src and src not in merged_sources:
                merged_sources.append(src)
            # 기존 멤버의 누적 출처도 승계
            for s in batch[mi].get("merged_sources", []):
                if s not in merged_sources:
                    merged_sources.append(s)
        consolidated.append({
            "category_major":  g.get("category_major") or rep_src.get("category_major", ""),
            "category_mid":    g.get("category_mid") or rep_src.get("category_mid", ""),
            "category_leaf":   g.get("canonical") or rep_src.get("category_leaf", ""),
            "screenshot_file": rep_src.get("screenshot_file", ""),
            "confidence":      rep_src.get("confidence", ""),
            "source_url":      rep_src.get("source_url", ""),
            "merged_sources":  merged_sources,
            "merged_count":    len(members),
        })

    # LLM이 누락한 번호는 개별 leaf로 보존 (손실 방지)
    for i, lf in enumerate(batch):
        if i not in assigned:
            consolidated.append(dict(lf))

    return consolidated
