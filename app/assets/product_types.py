"""제품 유형 ID 상수 및 매뉴얼 텍스트에서 유형 추정."""
from __future__ import annotations

PRODUCT_TYPES: dict[str, str] = {
    "BOARD_CMS":      "게시판/CMS",
    "USER_AUTH":      "회원/인증/로그인",
    "SHOPPING":       "쇼핑몰/전자상거래",
    "SEARCH":         "검색",
    "DASHBOARD":      "대시보드/분석",
    "FORM_WORKFLOW":  "폼/워크플로우",
    "OTHER":          "기타",
}

_KEYWORDS: dict[str, list[str]] = {
    "BOARD_CMS":  ["게시판", "게시글", "댓글", "공지사항", "첨부파일", "게시물"],
    "USER_AUTH":  ["회원", "로그인", "로그아웃", "비밀번호", "권한", "역할", "인증", "세션"],
    "SHOPPING":   ["주문", "결제", "장바구니", "배송", "재고", "상품", "구매"],
    "SEARCH":     ["검색", "필터", "정렬", "키워드", "검색어"],
    "DASHBOARD":  ["대시보드", "통계", "차트", "분석", "리포트"],
}


def classify_product_types(manual_text: str, min_keyword_hits: int = 2) -> list[str]:
    """매뉴얼 텍스트에서 제품 유형 추정 (키워드 기반).

    Phase 2에서 LLM 분류로 업그레이드 예정.
    """
    matched = []
    for ptype, keywords in _KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in manual_text)
        if hits >= min_keyword_hits:
            matched.append(ptype)
    return matched or ["OTHER"]
