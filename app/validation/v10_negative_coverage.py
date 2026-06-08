"""V10 — negative_category 커버리지 강제 (D49).

외부 제안 #4 (proposal-for-awt-claude §3.2, 5b) 채택.

leaf 유형별 적용 가능 negative 카테고리를 산출하고, TC들이 이를 충족하는지 검증.
- 각 leaf의 적용 카테고리 중 ≥ min_coverage 충족 (기본 0.6)
- 각 카테고리당 ≥ 1 TC 필수
- 적용 카테고리가 0인 leaf (예: read-only)는 V10 skip

설계: doc/03-tc-schema.md §7
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable


# D49 — 5 카테고리 enum
NEGATIVE_CATEGORIES = (
    "validation_failure",
    "duplicate_or_conflict",
    "permission_denied",
    "boundary_violation",
    "injection_or_security",
)


# leaf 유형 키워드 → 적용 카테고리 (doc/03-tc-schema.md §7.1)
# 우선순위: 첫 매칭 키워드를 사용. 키워드 없으면 [] → V10 skip.
_LEAF_KEYWORDS: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    # 파일 업로드 — 5종 중 3종
    (("업로드", "첨부", "파일"),
     ("validation_failure", "boundary_violation", "injection_or_security")),
    # 결제·주문 — 3종
    (("결제", "주문", "상품", "장바구니"),
     ("validation_failure", "duplicate_or_conflict", "permission_denied")),
    # 권한·인증 관리 — 2종
    (("권한", "로그아웃", "차단", "ip 차단", "비밀글"),
     ("permission_denied", "validation_failure")),
    # 조회·검색·필터 — 2종
    (("조회", "검색", "목록", "페이지", "필터"),
     ("permission_denied", "injection_or_security")),
    # 입력 폼 (가입·로그인·작성·수정·등록·삭제 — 가장 일반적) — 3종
    (("가입", "로그인", "작성", "등록", "수정", "변경", "삭제", "댓글", "찾기"),
     ("validation_failure", "duplicate_or_conflict", "boundary_violation")),
]


@dataclass
class V10Result:
    """V10 검증 결과 (leaf 단위)."""
    leaf_id: str           # requirement_id
    leaf_name: str         # category_leaf
    applicable: tuple[str, ...]   # 적용 가능 카테고리
    covered: tuple[str, ...]      # 실제 커버된 카테고리
    missing: tuple[str, ...]      # 누락 카테고리
    coverage_ratio: float
    passed: bool


def applicable_categories_for_leaf(leaf_name: str) -> tuple[str, ...]:
    """leaf 이름에서 적용 가능 negative 카테고리 추출.

    가장 먼저 매칭된 키워드의 카테고리 집합을 반환.
    매칭 키워드가 없으면 빈 튜플 (V10 skip 대상).
    """
    name_lower = leaf_name.lower()
    for keywords, categories in _LEAF_KEYWORDS:
        if any(k.lower() in name_lower for k in keywords):
            return categories
    return ()


def verify_leaf(
    leaf: dict,
    tcs_for_leaf: Iterable[dict],
    min_coverage: float = 0.6,
) -> V10Result:
    """단일 leaf의 V10 검증."""
    applicable = applicable_categories_for_leaf(leaf.get("category_leaf", ""))
    if not applicable:
        return V10Result(
            leaf_id=leaf.get("requirement_id", "?"),
            leaf_name=leaf.get("category_leaf", ""),
            applicable=(),
            covered=(),
            missing=(),
            coverage_ratio=1.0,  # 적용 카테고리 없으면 무조건 PASS
            passed=True,
        )

    covered_set: set[str] = set()
    for tc in tcs_for_leaf:
        tech = tc.get("design_technique", "")
        if not tech.startswith("negative_"):
            continue
        cat = tc.get("negative_category", "")
        if cat in applicable:
            covered_set.add(cat)

    covered = tuple(c for c in applicable if c in covered_set)
    missing = tuple(c for c in applicable if c not in covered_set)
    ratio = len(covered) / len(applicable) if applicable else 1.0
    passed = ratio >= min_coverage and len(covered) >= 1

    return V10Result(
        leaf_id=leaf.get("requirement_id", "?"),
        leaf_name=leaf.get("category_leaf", ""),
        applicable=applicable,
        covered=covered,
        missing=missing,
        coverage_ratio=ratio,
        passed=passed,
    )


def verify(
    tcs: list[dict],
    leaves: list[dict],
    min_coverage: float = 0.6,
) -> list[dict]:
    """전체 leaf에 대한 V10 검증. 실패한 leaf만 반환 (Stage 3 호환 형식).

    Returns:
        list of {tc_id, v, reason} — Stage 3._check_all와 동일 포맷
    """
    failures: list[dict] = []
    # leaf_id → TCs
    tcs_by_leaf: dict[str, list[dict]] = {}
    for tc in tcs:
        rid = tc.get("requirement_id", "")
        tcs_by_leaf.setdefault(rid, []).append(tc)

    for leaf in leaves:
        rid = leaf.get("requirement_id", "")
        result = verify_leaf(leaf, tcs_by_leaf.get(rid, []), min_coverage=min_coverage)
        if not result.passed:
            failures.append({
                "tc_id": f"LEAF:{rid}",
                "v": "V10",
                "reason": (
                    f"negative 카테고리 커버리지 부족 — "
                    f"적용 {result.applicable} / 커버 {result.covered} / 누락 {result.missing} "
                    f"(coverage {result.coverage_ratio:.0%}, 임계 {min_coverage:.0%})"
                ),
                # 구조화 필드 — stage3 _add_v10_tcs()에서 파싱 없이 사용
                "leaf_rid": rid,
                "leaf_name": result.leaf_name,
                "missing_categories": list(result.missing),
            })
    return failures


def report(tcs: list[dict], leaves: list[dict], min_coverage: float = 0.6) -> dict:
    """V10 통계 요약 (UI·로그·MANUAL.md에서 활용)."""
    tcs_by_leaf: dict[str, list[dict]] = {}
    for tc in tcs:
        rid = tc.get("requirement_id", "")
        tcs_by_leaf.setdefault(rid, []).append(tc)

    results = [verify_leaf(lf, tcs_by_leaf.get(lf.get("requirement_id", ""), []),
                            min_coverage=min_coverage)
               for lf in leaves]
    by_category: dict[str, int] = {c: 0 for c in NEGATIVE_CATEGORIES}
    for tc in tcs:
        cat = tc.get("negative_category", "")
        if cat in by_category:
            by_category[cat] += 1
    return {
        "leaf_count": len(leaves),
        "leaves_passed": sum(1 for r in results if r.passed),
        "leaves_failed": sum(1 for r in results if not r.passed),
        "leaves_skipped": sum(1 for r in results if not r.applicable),
        "tcs_by_category": by_category,
        "results": results,
    }
