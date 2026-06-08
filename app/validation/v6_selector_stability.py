"""V6 선택자 안정성 점수 — exec_confidence 보정 + 실패 원인 구분.

## 설계 목적
Stage 5 자동 실행 후 result=fail인 TC가 발생할 때, 두 가지 원인을 구분한다:
  (A) 선택자/UI 위치 변경 → 도구 오탐(false-fail). TC 자체는 유효.
  (B) 앱 로직 실패        → 실제 버그. 결함으로 보고.

실패 원인을 잘못 분류하면:
  - (A)를 (B)로 → 허위 결함 보고서 증가
  - (B)를 (A)로 → 실제 버그 은폐

## 선택자 안정성 계층 (Selector Stability Tier)

| 계층 | 예시 | 기본 점수 | 이유 |
|-----|------|---------|-----|
| L1 text_exact    | '로그인 성공' 문구 포함 | 0.92 | HTML 구조와 무관, UI 텍스트 변경만 영향 |
| L2 data_testid   | [data-testid="btn-submit"] | 0.88 | QA 목적 고정 속성, 리팩토링 안전 |
| L3 url_path      | /bbs/register.php         | 0.82 | URL 라우팅은 비교적 안정 |
| L4 id_selector   | #mb_id, #submit-btn       | 0.78 | ID는 안정적이나 동적 생성 ID 주의 |
| L5 class_stable  | .btn-primary, .error-msg  | 0.62 | CSS 리팩토링 시 깨짐 가능 |
| L6 aria_label    | [aria-label="닫기"]        | 0.72 | 접근성 속성, 비교적 안정 |
| L7 css_structural| div.container > ul > li   | 0.45 | 구조 변경에 취약 |
| L8 xpath         | //div[@id='wrap']/span    | 0.32 | 가장 취약, 리팩토링 즉시 깨짐 |
| L9 unknown       | 분류 불가                  | 0.55 | 기본값 |

## oracle 명료성 (Oracle Clarity)

기대 결과(expected)가 얼마나 객관적으로 검증 가능한가:
  - 인용 텍스트(따옴표/백틱) 포함: +0.20
  - URL 포함: +0.12
  - 상태 코드/버튼명 포함: +0.08
  - 토스트/메시지/팝업 언급: +0.05
  - 추상 표현('정상', '올바르게', '잘') 포함: -0.15
  - 너무 짧음(10자 미만): -0.10

## 실패 분류 (Failure Category)

result=fail인 TC에 대해:
  selector_unstable — 선택자 안정성 평균 < 0.55 → 도구 문제 의심
  oracle_mismatch   — oracle clarity < 0.50 → 기대 결과 모호해 판정 불가
  app_defect        — 선택자 안정, oracle 명확 → 실제 앱 버그 가능성 높음
  blocked           — result=blocked (네트워크/타임아웃) → 환경 문제
  not_applicable    — result != fail (pass/not_executed)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import NamedTuple


# ---------------------------------------------------------------------------
# 1. 선택자 패턴 추출
# ---------------------------------------------------------------------------

class SelectorHint(NamedTuple):
    tier: str          # L1~L9
    raw: str           # 추출된 원문
    score: float       # 기본 점수


# URL path 필터 — XPath 안의 HTML 태그 경로를 URL로 오분류하지 않도록
_HTML_TAGS: frozenset[str] = frozenset({
    "div", "span", "input", "form", "table", "tbody", "thead", "tfoot",
    "tr", "td", "th", "ul", "ol", "li", "a", "p", "h1", "h2", "h3",
    "h4", "h5", "h6", "button", "select", "option", "label", "section",
    "article", "header", "footer", "nav", "main", "aside", "figure",
    "canvas", "video", "audio", "img", "script", "style", "link",
    "textarea", "fieldset", "legend", "iframe", "small", "strong",
    "em", "br", "hr", "body", "html", "head", "meta", "title",
})


def _is_html_tag_path(raw: str) -> bool:
    """URL 후보가 HTML 태그 이름들로만 이루어진 경로면 True (XPath 오분류 방지)."""
    segments = [s.split("[")[0].split("(")[0]  # 인덱스·함수 제거
                for s in raw.strip("/").split("/") if s]
    return bool(segments) and all(seg.lower() in _HTML_TAGS for seg in segments)


_TIER_SCORES: dict[str, float] = {
    "text_exact":    0.92,
    "data_testid":   0.88,
    "url_path":      0.82,
    "id_selector":   0.78,
    "aria_label":    0.72,
    "class_stable":  0.62,
    "css_structural":0.45,
    "xpath":         0.32,
    "unknown":       0.55,
}

# 패턴 → (tier, 캡처그룹 인덱스)
_PATTERNS: list[tuple[re.Pattern, str]] = [
    # L8: XPath (//로 시작하거나 xpath= 접두어)
    (re.compile(r'xpath=([^\s,]+)', re.I),          "xpath"),
    (re.compile(r'(//[a-z]+\[@[^\]]+\][^\s,]*)', re.I), "xpath"),

    # L2: data-testid
    (re.compile(r'\[data-testid=["\']?([^"\'>\s]+)["\']?\]'), "data_testid"),
    (re.compile(r'data-testid=([^\s,]+)', re.I),    "data_testid"),

    # L6: aria-label
    (re.compile(r'\[aria-label=["\']([^"\']+)["\']?\]'), "aria_label"),

    # L4: #id
    (re.compile(r'(#[a-z_\-][a-z0-9_\-]+)', re.I), "id_selector"),

    # L5: .class (단독 또는 복합)
    (re.compile(r'(\.[a-z_\-][a-z0-9_\-]+(?:\.[a-z0-9_\-]+)*)', re.I), "class_stable"),

    # L7: 구조적 CSS (공백·> 포함)
    (re.compile(r'([a-z]+(?:\s*[>+~]\s*[a-z]+)+)', re.I), "css_structural"),

    # L3: URL 경로 — .php 확장자 포함 URL (gnuboard5 등 PHP 앱)
    #   주의: XPath 안의 /ul/li 같은 구조 경로를 잘못 분류하지 않도록
    #   (1) .php 포함 URL — 가장 명확한 URL 패턴
    (re.compile(r'(/[a-z0-9_\-/]+\.php[^\s,\)]*)', re.I), "url_path"),
    #   (2) 4자 이상 세그먼트를 포함하는 URL (/api/users, /bbs/board 등)
    #       HTML 태그(div,ul,li,span,tr,td 등)는 3자 이하라 제외됨
    (re.compile(r'(/(?:[a-z0-9][a-z0-9_\-]{3,}/)*[a-z0-9][a-z0-9_\-]{3,})', re.I), "url_path"),

    # L1: 따옴표/백틱으로 묶인 UI 검증 텍스트 (기대 문구)
    #   '=' 바로 뒤에 오는 따옴표는 XPath/CSS 속성값 → 제외 (부정형 후방탐색)
    (re.compile(r'(?<!=)[\'"`]([가-힣a-zA-Z0-9\s]{4,40})[\'"`]'), "text_exact"),
]


def extract_selectors(text: str) -> list[SelectorHint]:
    """텍스트(precondition / expected)에서 선택자 힌트를 추출한다."""
    hints: list[SelectorHint] = []
    seen: set[str] = set()

    for pattern, tier in _PATTERNS:
        for m in pattern.finditer(text):
            raw = m.group(1) if m.lastindex else m.group(0)
            raw = raw.strip()
            key = (tier, raw)
            if key in seen:
                continue
            if tier == "url_path":
                # (1) HTML 태그로만 구성된 경로 제외 (XPath 구조 오분류 방지)
                if _is_html_tag_path(raw):
                    continue
                # (2) 이미 XPath 힌트로 캡처된 문자열의 부분 문자열이면 제외
                #     예: xpath=//span[@id='z']/text() 안의 /text 는 URL이 아님
                if any(raw in h.raw for h in hints if h.tier == "xpath"):
                    continue
            seen.add(key)
            hints.append(SelectorHint(tier=tier, raw=raw,
                                      score=_TIER_SCORES[tier]))
    return hints


def selector_stability_score(hints: list[SelectorHint]) -> float:
    """힌트 목록의 가중 평균 안정성 점수 (0~1). 힌트 없으면 0.60."""
    if not hints:
        return 0.60
    # 상위 계층 힌트가 더 큰 영향 → 점수 자체를 가중치로 사용
    weighted = sum(h.score * h.score for h in hints)   # 높은 점수 = 더 큰 가중치
    total    = sum(h.score for h in hints)
    return round(weighted / total, 3)


# ---------------------------------------------------------------------------
# 2. oracle 명료성
# ---------------------------------------------------------------------------

_ABSTRACT_TERMS = re.compile(
    r'정상|올바르게|올바른|잘\s|제대로|적절히|적절한|잘못|올바르지\s*않', re.I
)
_QUOTED_TEXT    = re.compile(r'[\'"`][가-힣a-zA-Z0-9\s]{4,}[\'"`]')
_URL_IN_TEXT    = re.compile(r'/[a-z0-9_\-/]+\.php')
_STATE_KEYWORDS = re.compile(r'버튼|토스트|팝업|모달|메시지|오류|alert|toast|modal', re.I)
_STATUS_CODE    = re.compile(r'\b(200|400|403|404|500)\b')


def oracle_clarity_score(expected: str) -> float:
    """기대 결과 텍스트의 검증 명료성 점수 (0~1). 기준 0.60."""
    score = 0.60

    if len(expected) < 10:
        score -= 0.10
    if _QUOTED_TEXT.search(expected):
        score += 0.20
    if _URL_IN_TEXT.search(expected):
        score += 0.12
    if _STATE_KEYWORDS.search(expected):
        score += 0.05
    if _STATUS_CODE.search(expected):
        score += 0.08
    if _ABSTRACT_TERMS.search(expected):
        score -= 0.15

    return round(max(0.0, min(1.0, score)), 3)


# ---------------------------------------------------------------------------
# 3. 종합 exec_confidence 계산
# ---------------------------------------------------------------------------

def compute_exec_confidence(
    tc: dict,
    retry_count: int = 0,
    max_retries: int = 3,
) -> float:
    """
    exec_confidence = selector_stability × 0.50
                    + oracle_clarity     × 0.35
                    + retry_penalty      × 0.15

    retry_penalty = 1.0 if retry_count == 0 else 1.0 - retry_count/max_retries
    """
    precondition = tc.get("precondition", "") or ""
    expected     = tc.get("expected", "") or ""
    combined     = precondition + " " + expected

    hints     = extract_selectors(combined)
    stability = selector_stability_score(hints)
    clarity   = oracle_clarity_score(expected)
    retry_penalty = 1.0 if retry_count == 0 else max(0.0, 1.0 - retry_count / max_retries)

    raw = stability * 0.50 + clarity * 0.35 + retry_penalty * 0.15
    return round(max(0.0, min(1.0, raw)), 3)


# ---------------------------------------------------------------------------
# 4. 실패 분류
# ---------------------------------------------------------------------------

FAILURE_CATEGORIES = {
    "app_defect":        "앱 로직 결함 (선택자 안정, oracle 명확)",
    "selector_unstable": "선택자/UI 위치 변경으로 인한 도구 오탐",
    "oracle_mismatch":   "기대 결과 모호 — oracle 재정의 필요",
    "blocked":           "네트워크/타임아웃/환경 문제",
    "not_applicable":    "실패 아님 (pass / not_executed)",
}

_SELECTOR_UNSTABLE_THRESHOLD = 0.55
_ORACLE_MISMATCH_THRESHOLD   = 0.50


def classify_failure(tc: dict, retry_count: int = 0) -> str:
    """result=fail인 TC의 실패 원인을 분류한다."""
    result = tc.get("result", "not_executed")

    if result == "blocked":
        return "blocked"
    if result != "fail":
        return "not_applicable"

    precondition = tc.get("precondition", "") or ""
    expected     = tc.get("expected", "") or ""
    combined     = precondition + " " + expected

    hints     = extract_selectors(combined)
    stability = selector_stability_score(hints)
    clarity   = oracle_clarity_score(expected)

    if stability < _SELECTOR_UNSTABLE_THRESHOLD:
        return "selector_unstable"
    if clarity < _ORACLE_MISMATCH_THRESHOLD:
        return "oracle_mismatch"
    return "app_defect"


# ---------------------------------------------------------------------------
# 5. TC 목록 일괄 보정 (Stage 5 출력에 적용)
# ---------------------------------------------------------------------------

@dataclass
class V6Report:
    total: int = 0
    annotated: int = 0
    by_failure_category: dict[str, int] = field(default_factory=dict)
    avg_selector_stability: float = 0.0
    avg_oracle_clarity: float = 0.0
    avg_exec_confidence: float = 0.0


def annotate(
    tcs: list[dict],
    retry_counts: dict[str, int] | None = None,
    overwrite_exec_confidence: bool = True,
) -> tuple[list[dict], V6Report]:
    """
    TC 목록에 V6 점수를 주석(annotation)으로 추가한다.

    추가/갱신되는 필드:
      selector_stability_score  — 선택자 안정성 (0~1)
      oracle_clarity_score      — oracle 명료성 (0~1)
      exec_confidence           — 종합 신뢰도 (Stage 5 값 덮어씀, overwrite=True 기본)
      failure_category          — 실패 분류 문자열 (result=fail인 경우만 의미있음)
      selector_hints            — 추출된 선택자 힌트 목록 (디버그용)
    """
    if retry_counts is None:
        retry_counts = {}

    stability_sum = 0.0
    clarity_sum   = 0.0
    conf_sum      = 0.0
    cat_counts: dict[str, int] = {}

    for tc in tcs:
        tc_id        = tc.get("tc_id", "")
        precondition = tc.get("precondition", "") or ""
        expected     = tc.get("expected", "") or ""
        combined     = precondition + " " + expected

        hints     = extract_selectors(combined)
        stability = selector_stability_score(hints)
        clarity   = oracle_clarity_score(expected)
        retry_n   = retry_counts.get(tc_id, 0)
        confidence= compute_exec_confidence(tc, retry_count=retry_n)
        category  = classify_failure(tc, retry_count=retry_n)

        tc["selector_stability_score"] = stability
        tc["oracle_clarity_score"]     = clarity
        tc["failure_category"]         = category
        tc["selector_hints"] = [
            {"tier": h.tier, "raw": h.raw, "score": h.score} for h in hints
        ]
        if overwrite_exec_confidence:
            tc["exec_confidence"] = confidence

        stability_sum += stability
        clarity_sum   += clarity
        conf_sum      += confidence
        cat_counts[category] = cat_counts.get(category, 0) + 1

    n = len(tcs)
    report = V6Report(
        total=n,
        annotated=n,
        by_failure_category=cat_counts,
        avg_selector_stability=round(stability_sum / n, 3) if n else 0.0,
        avg_oracle_clarity=round(clarity_sum / n, 3) if n else 0.0,
        avg_exec_confidence=round(conf_sum / n, 3) if n else 0.0,
    )
    return tcs, report


# ---------------------------------------------------------------------------
# 6. 리포트 출력 헬퍼
# ---------------------------------------------------------------------------

def format_report(report: V6Report) -> str:
    lines = [
        f"V6 선택자 안정성 분석 — TC {report.total}개",
        f"  평균 selector_stability : {report.avg_selector_stability:.3f}",
        f"  평균 oracle_clarity     : {report.avg_oracle_clarity:.3f}",
        f"  평균 exec_confidence    : {report.avg_exec_confidence:.3f}",
        "",
        "  실패 분류:",
    ]
    for cat, cnt in sorted(report.by_failure_category.items(), key=lambda x: -x[1]):
        desc = FAILURE_CATEGORIES.get(cat, cat)
        lines.append(f"    {cat:<22} {cnt:>4}건  — {desc}")
    return "\n".join(lines)
