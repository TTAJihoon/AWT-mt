"""카테고리 통제 어휘(taxonomy) — D52.

문제(C2): DOM_SPEC·CONSOLIDATE·TC_DESIGN이 `category_major`를 자유 서술하여
같은 도메인이 수백 종으로 파편화됨(실측 436종). 특히 인증 도메인이
"User Management"/"Authentication"/"Account Management" 등으로 분열되어
로그인 편중이 과장되고, Stage 1 dedup이 "다른 대분류=다른 기능"으로 오판함.

해소:
  1) (주 기제) 프롬프트에 고정 목록을 주입해 LLM이 목록 중 선택하도록 강제.
  2) (안전망) coerce_major()로 목록 밖 값을 동의어 규칙으로 보정. 매칭 실패 시
     원본 유지(정보 손실 0) + unknown 샘플 기록 → 어휘 보강 근거.

원칙: 대분류(major)만 통제. 중분류·소분류(leaf)는 그대로 → 시험 커버리지 손실 없음.
"""
from __future__ import annotations

TAXONOMY_VERSION = "v1"

# 고정 대분류 12종 (웹 일반 + ISO 25023 친화, 한국어 고정)
TAXONOMY: list[str] = [
    "회원·인증",       # 로그인/로그아웃/계정/회원가입/프로필 — 분열되던 인증 도메인 통합
    "게시판·콘텐츠",   # 게시글/댓글/커뮤니티/에디터/콘텐츠
    "검색·필터",       # 검색/필터/정렬
    "네비게이션·메뉴", # 메뉴/링크/헤더/푸터/사이드바/레이아웃/이동
    "UI·접근성",       # UI 컨트롤/사용성/접근성/반응형/표시 설정
    "결제·쇼핑",       # 장바구니/주문/결제/상품/쿠폰/위시리스트
    "폼·입력검증",     # 폼/입력/검증/제출
    "알림·고객지원",   # 알림/공지/문의/FAQ/고객지원
    "관리자",          # 관리자/운영
    "정보표시·정책",   # 정보 표시/약관/정책/통계/개인정보
    "설정·환경",       # 환경설정/개인화/디바이스 설정
    "기타",            # 분류 불가 fallback
]
TAXONOMY_SET = set(TAXONOMY)

# ── 2축 분리 (아이디어 A) ─────────────────────────────────────────────────────
# taxonomy 12종은 두 직교 축을 섞고 있었다:
#   - 제품 도메인 축: 회원·인증 / 게시판·콘텐츠 / 검색·필터 / 결제·쇼핑 / 관리자 /
#                     알림·고객지원 / 정보표시·정책 / 설정·환경
#   - 상호작용 유형 축: 폼·입력검증 / UI·접근성 / 네비게이션·메뉴
# 회원가입은 *도메인=회원·인증*이며 동시에 *유형=폼*이라, LLM이 유형을 고르면
# 대분류가 폼·입력검증으로 붕괴됐다(실측 98/108). 또 메뉴 링크가 네비게이션 도메인으로
# 257개 뭉쳤다. → 대분류는 '도메인 우선'으로 분류하고, 도메인이 없을 때만 상호작용
# 유형을 쓴다. leaf·중분류까지 함께 보아 도메인 신호를 최대한 살린다.

# 도메인 규칙 (우선 평가) — 더 구체적·중요한 도메인을 앞에 둔다.
_DOMAIN_RULES: list[tuple[str, list[str]]] = [
    ("회원·인증", [
        "login", "logout", "log in", "log out", "sign in", "sign out", "signin", "signout",
        "authentication", "auth", "session", "password", "credential", "identity",
        "account", "member", "register", "registration", "sign up", "signup", "profile",
        "my page", "mypage", "my-page", "access control", "security",
        "user management", "user account", "user profile", "user personalization",
        "user communication", "user engagement", "user assistance", "user support",
        "user info", "user center",
        "로그인", "로그아웃", "인증", "세션", "비밀번호", "계정", "회원", "가입",
        "프로필", "마이페이지", "탈퇴", "로그", "권한", "보안",
    ]),
    ("결제·쇼핑", [
        "shopping", "shop", "cart", "wishlist", "checkout", "order", "payment", "pay ",
        "commerce", "coupon", "product", "catalog", "promotion", "loyalty", "reward",
        "points", "discount",
        "쇼핑", "장바구니", "결제", "주문", "상품", "쿠폰", "위시리스트", "위시",
        "카트", "포인트", "할인", "적립",
    ]),
    ("검색·필터", [
        "search", "filter", "sort", "ranking", "discovery", "retrieval",
        "검색", "필터", "정렬", "찾기",
    ]),
    ("게시판·콘텐츠", [
        "board", "bbs", "post", "comment", "community", "editor", "article", "content",
        "writing", "authoring", "reading", "browsing",
        "게시판", "게시글", "게시물", "댓글", "글쓰기", "글 작성", "콘텐츠",
        "커뮤니티", "작성", "에디터", "글 ", "읽기",
    ]),
    ("알림·고객지원", [
        "notification", "notice", "inquiry", "faq", "support", "customer", "qna", "q&a",
        "messaging", "communication",
        "알림", "공지", "문의", "고객지원", "고객", "쪽지", "메시지",
    ]),
    ("관리자", [
        "admin", "administration", "관리자", "운영",
    ]),
    ("정보표시·정책", [
        "information", "legal", "policy", "terms", "privacy", "statistics",
        "analytics", "metrics", "trust",
        "정책", "약관", "통계", "개인정보", "법적", "안내",
    ]),
    ("설정·환경", [
        "settings", "preference", "configuration", "personalization",
        "customization", "localization",
        "설정", "환경", "개인화", "맞춤",
    ]),
]

# 상호작용 유형 규칙 (도메인 미매칭 시에만 평가)
_INTERACTION_RULES: list[tuple[str, list[str]]] = [
    ("UI·접근성", [
        "accessibility", "usability", "responsive", "device", "typography", "readability",
        "user interface", "interface", "ui ", "ui/", "ui:", "ux", "display", "panel",
        "layout",
        "접근성", "사용성", "반응형", "디바이스", "표시", "가독성",
        "사용자 인터페이스", "사용자인터페이스", "레이아웃", "패널",
    ]),
    ("폼·입력검증", [
        "form", "input", "validation", "submission", "submit",
        "폼", "입력", "검증", "제출", "양식",
    ]),
    ("네비게이션·메뉴", [
        "navigation", "navigaton", "navigaiton", "nav", "menu", "link", "header",
        "footer", "sidebar", "breadcrumb", "site", "page", "web",
        "네비", "메뉴", "탐색", "이동", "헤더", "푸터", "링크", "사이트", "홈",
    ]),
]

# fallback (도메인·상호작용 모두 미매칭 시) — ISO 품질특성명 오용 등 → 기타
_FALLBACK_RULES: list[tuple[str, list[str]]] = [
    ("기타", [
        "기타", "other", "misc", "etc", "utility", "utilities", "general", "common",
        "platform", "system", "meta",
        "functional suitability", "functionality", "기능 적합성", "기능적합성",
        "suitability",
    ]),
]

DOMAIN_MAJORS = [r[0] for r in _DOMAIN_RULES]
INTERACTION_MAJORS = [r[0] for r in _INTERACTION_RULES]
_DOMAIN_SET = set(DOMAIN_MAJORS)
_INTERACTION_SET = set(INTERACTION_MAJORS)

# 하위호환: 기존 _RULES(도메인→상호작용→fallback 순서)
_RULES = _DOMAIN_RULES + _INTERACTION_RULES + _FALLBACK_RULES


# 문서 제목/메타 문자열 토큰 — 제품 도메인이 아니다. 통제 어휘 키워드 매칭
# '전에' 걸러낸다. (예: "그누보드5 기능 명세서 (AWT Stage 1 입력용)"의 '입력'이
# 폼·입력검증으로 오매칭되어 모든 leaf 대분류가 폼·입력검증으로 붕괴되던 문제 차단.)
# 토큰은 명백히 문서 메타인 것만 보수적으로 선정(도메인명 오탐 방지).
_META_TITLE_TOKENS = (
    "명세서", "기능 명세", "기능명세", "specification",
    "입력용", "참고문서", "참고 문서", "requirements doc",
)


def classify_major(name: str, mid: str = "", leaf: str = "") -> tuple[str, str]:
    """대분류를 '제품 도메인 우선'으로 분류 (2축 분리, 아이디어 A).

    name(대분류)뿐 아니라 mid(중분류)·leaf(소분류)까지 함께 보아 도메인 신호를
    최대한 살린다. 예) name="폼·입력검증" + leaf="회원가입" → 도메인 '회원·인증' 우선.

    우선순위:
        1) name이 이미 도메인 통제어휘 → 그대로(canonical)
        2) leaf+mid+name 전체에서 도메인 키워드 매칭 → 해당 도메인(coerced)
        3) 문서 메타 문자열 → 기타(coerced)
        4) name이 상호작용 통제어휘 → 그대로(canonical)
        5) 상호작용 키워드 매칭 → 해당 유형(coerced)
        6) fallback 키워드 → 기타(coerced)
        7) 매칭 실패 → 원본 유지(unknown)

    Returns:
        (canonical, status) — status ∈ {"canonical", "coerced", "unknown"}.
    """
    raw = (name or "").strip()
    if raw in _DOMAIN_SET:
        return raw, "canonical"

    blob = " ".join([leaf or "", mid or "", raw]).lower()

    # 2) 도메인 우선 (leaf+mid+major 전체 대상)
    for canon, kws in _DOMAIN_RULES:
        for kw in kws:
            if kw and kw in blob:
                return canon, "coerced"

    # 3) 문서 메타 → 기타 (도메인 신호가 없을 때만 도달)
    if any(tok in blob for tok in _META_TITLE_TOKENS):
        return "기타", "coerced"

    # 4) name이 상호작용 통제어휘면 유지
    if raw in _INTERACTION_SET:
        return raw, "canonical"

    # 5) 상호작용 매칭
    for canon, kws in _INTERACTION_RULES:
        for kw in kws:
            if kw and kw in blob:
                return canon, "coerced"

    # 6) fallback
    for canon, kws in _FALLBACK_RULES:
        for kw in kws:
            if kw and kw in blob:
                return canon, "coerced"

    if not raw:
        return "기타", "coerced"
    return raw, "unknown"


def coerce_major(name: str) -> tuple[str, str]:
    """대분류명을 통제 어휘로 보정 (하위호환 래퍼 — classify_major(name)).

    leaf·mid 컨텍스트 없이 대분류명만으로 분류. 신규 코드는 classify_major를 직접 호출해
    leaf까지 전달하면 도메인 분류 정확도가 높다.
    """
    return classify_major(name)
