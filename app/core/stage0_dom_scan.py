"""Stage 0 — Playwright DOM 스캔 → LLM 명세 초안 (D32·D33).

변경 이력:
  - DOM elements를 _CHUNK_SIZE(50)개 단위로 분할 → DOM_SPEC 복수 호출로 12000자 제한 해소
  - 페이지별 스크린샷 저장 (dom-scan/screenshots/)
  - 각 feature에 screenshot_file 필드 추가
  - DOM_SPEC 오류 시 최대 3회 재시도; 전체 features=0이면 RuntimeError 발생
"""
from __future__ import annotations
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Callable

from playwright.sync_api import sync_playwright, Page

_ALLOWED_ATTRS   = {"id", "name", "type", "placeholder", "aria-label", "href"}
_INTERACTIVE_TAGS = {"a", "button", "input", "select", "textarea", "form", "label"}

# 청크 1개당 DOM 요소 수 — 50개 × ~100자 ≈ 5,000자 → max_input_tokens(8,000)에 여유 있게 맞춤
_CHUNK_SIZE       = 50
# DOM_SPEC 오류 시 청크별 최대 재시도 횟수
_CHUNK_MAX_RETRY  = 3


def _extract_elements(page: Page) -> list[dict]:
    return page.evaluate("""() => {
        const tags = ['a','button','input','select','textarea','form','label','h1','h2','h3','nav'];
        const navSel = 'nav, header, footer, [role="navigation"], [role="menu"],'
                     + ' #gnb, .gnb, #snb, .snb, #lnb, .lnb, #menu, .menu,'
                     + ' #header, .header, #footer, .footer, #nav, .nav';
        const results = [];
        for (const tag of tags) {
            for (const el of document.querySelectorAll(tag)) {
                const obj = {tag};
                const keep = ['id','name','type','placeholder','aria-label','href'];
                for (const attr of keep) {
                    const v = el.getAttribute(attr);
                    if (v) obj[attr] = v.substring(0, 100);
                }
                const text = el.innerText?.trim().substring(0, 80);
                if (text) obj.text = text;
                // 네비게이션 컨테이너(헤더/푸터/메뉴) 내부인지 — 순수 이동 링크 축약용
                try { if (el.closest && el.closest(navSel)) obj.in_nav = true; } catch (e) {}
                results.push(obj);
            }
        }
        return results;
    }""")


def _chunk_elements(elements: list[dict], chunk_size: int = _CHUNK_SIZE) -> list[list[dict]]:
    """DOM 요소 목록을 chunk_size 단위 배치로 분할."""
    return [elements[i : i + chunk_size] for i in range(0, max(len(elements), 1), chunk_size)]


# ── 전역 컴포넌트 dedup (D51) ─────────────────────────────────────────────────
# 헤더·푸터·네비처럼 여러 페이지에 동일 셀렉터로 반복되는 요소를 1회만 명세하기 위한
# 규칙 기반(LLM 불필요) 탐지. GnuBoard5 헤더 로그인 박스가 44/89 페이지에서 중복
# 추출되어 인증 도메인 TC가 ~30%로 과대표집되던 문제(C1) 해소.
# 실측: GnuBoard5 로그인 폼은 44/89(49.4%) 페이지에 등장 → 로그인 상태 전환으로
# 헤더가 절반만 노출되므로, 0.5(임계 45)면 로그인(44)을 놓친다. 0.4(임계 36)로
# 잡되, 페이지 고유 콘텐츠(고유 지문)는 40%에 못 미쳐 과병합되지 않는다.
_GLOBAL_RATIO_DEFAULT      = 0.4   # 이 비율 이상 페이지에 등장하면 전역으로 판정
_MIN_PAGES_FOR_GLOBAL      = 5     # 페이지 모수가 이보다 적으면 전역 탐지 비활성(오탐 방지)


def _norm_text(s: str) -> str:
    """전역 지문용 텍스트 정규화 — 공백 축약·소문자·길이 제한."""
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s[:60]


def _element_signature(el: dict):
    """전역 컴포넌트 판정용 지문 = (tag, id, name, type, normalized_text).

    - href는 쿼리·앵커 변동이 커서 제외(같은 네비 링크라도 페이지마다 달라질 수 있음).
    - id/name/text 중 하나라도 있어야 '식별 가능' → 전역 후보.
      셋 다 없는 익명 요소(예: 라벨 없는 입력칸)는 None을 반환해 전역에서 제외 →
      서로 다른 의미의 익명 요소가 한 덩어리로 과병합되는 것을 방지.
    """
    id_   = (el.get("id", "") or "").strip()
    name  = (el.get("name", "") or "").strip()
    text  = _norm_text(el.get("text", ""))
    if not (id_ or name or text):
        return None
    return (
        el.get("tag", ""),
        id_,
        name,
        (el.get("type", "") or "").strip(),
        text,
    )


def _detect_global_components(
    page_elements_list: list[list[dict]],
    ratio: float,
    min_pages: int,
) -> tuple[set, dict]:
    """여러 페이지에 동일 지문으로 반복되는 요소를 전역으로 판정.

    Returns:
        (global_sigs, report) — global_sigs는 전역 지문 집합.
    """
    n_pages = len(page_elements_list)
    if n_pages < min_pages:
        return set(), {
            "enabled": False,
            "reason": f"pages({n_pages})<min({min_pages})",
            "total_pages": n_pages,
        }

    presence: Counter = Counter()
    for elements in page_elements_list:
        seen = set()
        for el in elements:
            sig = _element_signature(el)
            if sig is not None:
                seen.add(sig)
        for sig in seen:
            presence[sig] += 1

    threshold = max(2, math.ceil(n_pages * ratio))  # 최소 2개 페이지 공통이어야 전역
    global_sigs = {sig for sig, c in presence.items() if c >= threshold}
    report = {
        "enabled": True,
        "total_pages": n_pages,
        "ratio": ratio,
        "threshold_pages": threshold,
        "global_signatures": len(global_sigs),
    }
    return global_sigs, report


# ── 네비게이션 링크 축약 (아이디어 1) ────────────────────────────────────────
# nav/header/footer/메뉴 컨테이너 내 '순수 이동 링크'(텍스트+href만 있고 시험 가치가
# 낮은 메뉴 항목)는 수십~수백 개가 모두 별도 기능으로 추출되어 네비게이션·메뉴 도메인을
# 비대하게 만든다(실측 257개/23.8%). 시험 관점에서 "메뉴 이동이 동작한다"는 대표 몇 개로
# 충분하므로, DOM_SPEC 호출 '전에' 대표 N개만 남기고 축약한다(LLM 호출·기능 수 동시 절감).
# 단, 로그인·장바구니·결제·검색 등 '중요 액션' 링크는 절대 축약하지 않는다.
_NAV_LINK_KEEP_DEFAULT = 8

# 순수 네비게이션이 아니라 '기능 액션'으로 보존할 키워드 (텍스트/href/id/aria 부분일치)
_NAV_KEEP_ACTIONS = (
    "login", "logout", "join", "register", "signup", "sign-up", "mypage", "my-page",
    "cart", "wishlist", "order", "checkout", "pay", "search", "write", "delete",
    "modify", "update", "upload", "download", "reply", "comment", "admin", "password",
    "로그인", "로그아웃", "가입", "회원", "마이페이지", "장바구니", "위시", "주문",
    "결제", "검색", "글쓰기", "글 작성", "작성", "등록", "수정", "삭제", "답변",
    "댓글", "다운로드", "업로드", "관리자", "신고", "비밀번호",
)


def _is_pure_nav_link(el: dict) -> bool:
    """nav 컨테이너 내 단순 이동 링크인지 — 축약 대상(시험 가치 낮음).

    중요 액션(로그인·장바구니·결제·검색 등) 키워드가 텍스트/href/id/aria에 있으면
    기능 링크로 보고 축약하지 않는다(보존).
    """
    if el.get("tag") != "a" or not el.get("in_nav") or not el.get("href"):
        return False
    blob = " ".join(str(el.get(k, "")) for k in ("text", "href", "id", "aria-label")).lower()
    if any(kw in blob for kw in _NAV_KEEP_ACTIONS):
        return False
    return True


def _collapse_nav_links(elements: list[dict], keep: int) -> tuple[list[dict], int, list[str]]:
    """순수 nav 링크를 정규화 텍스트 기준 대표 keep개로 축약.

    Returns:
        (kept_elements, dropped_count, dropped_samples)
        — nav가 아닌 요소는 모두 보존. nav 링크는 distinct 텍스트 기준 앞쪽 keep개만 유지.
    """
    nav, others = [], []
    for el in elements:
        (nav if _is_pure_nav_link(el) else others).append(el)

    seen: dict = {}          # norm_text → kept(el) or None(over-limit, 이후 동일텍스트도 drop)
    kept_nav: list[dict] = []
    dropped = 0
    samples: list[str] = []
    for el in nav:
        t = _norm_text(el.get("text", "")) or _norm_text(el.get("href", ""))
        if t in seen:
            dropped += 1
            continue
        if len(kept_nav) < keep:
            seen[t] = el
            kept_nav.append(el)
        else:
            seen[t] = None
            dropped += 1
            if len(samples) < 10:
                samples.append((el.get("text", "") or el.get("href", ""))[:40])
    return others + kept_nav, dropped, samples


def _safe_filename(url: str, base_url: str) -> str:
    """URL 경로를 파일명용 안전 문자열로 변환 (최대 40자)."""
    path = url.replace(base_url, "").strip("/") or "home"
    return re.sub(r"[^\w\-]", "_", path)[:40]


def scan(
    url: str,
    llm_client,
    run_dir: Path,
    auth_sequence: list[dict] | None = None,
    max_pages: int = 30,
    progress_cb: Callable[[str], None] | None = None,
    selected_urls: list[str] | None = None,
    cached_features: dict[str, list[dict]] | None = None,
    should_stop: Callable[[], bool] | None = None,
    dedup_global_components: bool = True,
    global_ratio: float = _GLOBAL_RATIO_DEFAULT,
    min_pages_for_global: int = _MIN_PAGES_FOR_GLOBAL,
    collapse_nav_links: bool = True,
    nav_link_keep: int = _NAV_LINK_KEEP_DEFAULT,
) -> dict:
    """URL을 스캔해 feature-spec-draft.md 생성. LLM 명세 초안 반환.

    Args:
        url:             시작 URL (BFS 기준)
        max_pages:       BFS 최대 페이지 수 (selected_urls가 있으면 무시)
        selected_urls:   None이면 기존 BFS 방식. 리스트면 그 URL만 처리(BFS 생략).
        cached_features: {url: [features...]} — 이 URL은 LLM 호출 생략, 캐시 features 그대로 사용.

    Raises:
        RuntimeError: 모든 페이지 스캔 후 features가 0개인 경우
                      (LLM API 오류·키 오류 등 원인 가능성 높음)
    """
    out_dir = run_dir / "dom-scan"
    out_dir.mkdir(parents=True, exist_ok=True)

    screenshots_dir = out_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    all_features: list[dict] = []
    page_specs: list[dict] = []  # Pass 1 수집: [{url, screenshot, elements}] (전역 dedup 후 Pass 2에서 DOM_SPEC)
    visited: set[str] = set()
    llm_error_count = 0          # LLM 호출 실패 누적
    llm_call_count  = 0          # LLM 호출 성공 누적
    cache_hit_count = 0          # 캐시 재사용 페이지 수

    cached_features = cached_features or {}

    def _cb(msg: str):
        if progress_cb:
            progress_cb(msg)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page    = context.new_page()

        _cb(f"접속 중: {url}")
        page.goto(url, wait_until="networkidle", timeout=30000)

        # 인증 시퀀스 (D33 — 하드코딩 금지, 실행 시점 입력)
        if auth_sequence:
            for step in auth_sequence:
                action = step.get("action")
                if action == "fill":
                    page.fill(step["selector"], step["value"])
                elif action == "click":
                    page.click(step["selector"])
                    page.wait_for_load_state("networkidle", timeout=10000)
            _cb("인증 완료")

        # ── 페이지 큐 결정 ────────────────────────────────────────────────────
        # selected_urls가 주어지면 그것만 처리(BFS 생략), 아니면 기존 BFS
        if selected_urls is not None:
            queue: list[tuple[str, int]] = [(u, 0) for u in selected_urls]
            do_bfs = False
            total_pages = len(selected_urls)
        else:
            queue = [(url, 0)]
            do_bfs = True
            total_pages = max_pages

        while queue and len(visited) < total_pages:
            # 사용자 중단 협력 체크 (다음 페이지 시작 전)
            if should_stop and should_stop():
                _cb("⏹ 사용자 중단 — 페이지 분석 종료")
                break
            cur_url, depth = queue.pop(0)
            if cur_url in visited:
                continue
            visited.add(cur_url)

            # ── 캐시 hit: LLM 호출 생략 ────────────────────────────────────
            if cur_url in cached_features:
                cached = cached_features[cur_url]
                # 캐시된 feature를 그대로 추가 (source_url 보존)
                for feat in cached:
                    f = dict(feat)
                    f.setdefault("source_url", cur_url)
                    all_features.append(f)
                cache_hit_count += 1
                page_idx = len(visited)
                _cb(
                    f"♻ 캐시 재사용 ({page_idx}/{total_pages}): "
                    f"{cur_url} — 기능 {len(cached)}개"
                )
                continue

            try:
                if cur_url != page.url:
                    page.goto(cur_url, wait_until="networkidle", timeout=20000)

                page_idx = len(visited)
                _cb(f"스캔 중 ({page_idx}/{total_pages}): {cur_url}")

                # ── 스크린샷 저장 ────────────────────────────────────────────
                screenshot_name = f"page_{page_idx:03d}_{_safe_filename(cur_url, url)}.png"
                try:
                    page.screenshot(
                        path=str(screenshots_dir / screenshot_name),
                        full_page=True,
                    )
                    _cb(f"  스크린샷 저장: {screenshot_name}")
                except Exception as ss_err:
                    _cb(f"  스크린샷 실패 (무시): {ss_err}")
                    screenshot_name = ""

                # ── DOM 요소 추출 (Pass 1: 수집만, DOM_SPEC는 전역 dedup 후) ──
                elements = _extract_elements(page)
                if not elements:
                    _cb(f"  DOM 요소 없음 — 스킵: {cur_url}")
                    continue
                page_specs.append({
                    "url":        cur_url,
                    "screenshot": screenshot_name,
                    "elements":   elements,
                })
                _cb(f"  DOM 요소 {len(elements)}개 수집")

                # 같은 origin 링크 수집 (depth+1) — selected_urls 모드에서는 생략
                if do_bfs and depth < 2:
                    links = page.evaluate(
                        "() => [...document.querySelectorAll('a[href]')].map(a=>a.href)"
                    )
                    for lnk in links:
                        if lnk.startswith(url) and lnk not in visited:
                            queue.append((lnk, depth + 1))

            except Exception as e:
                _cb(f"  페이지 스킵 ({cur_url}): {e}")

        browser.close()

    # ── Pass 2: 전역 컴포넌트 dedup 후 DOM_SPEC (D51) ─────────────────────────
    def _spec_elements(elements, src_url, screenshot, scope, label):
        """주어진 요소 묶음을 청크로 나눠 DOM_SPEC 호출 → all_features에 적재."""
        nonlocal llm_call_count, llm_error_count
        chunks = _chunk_elements(elements)
        count = 0
        for chunk_idx, chunk in enumerate(chunks, 1):
            if should_stop and should_stop():
                _cb("⏹ 사용자 중단 — DOM_SPEC 종료")
                break
            success = False
            for attempt in range(1, _CHUNK_MAX_RETRY + 1):
                try:
                    result = llm_client.call("DOM_SPEC", {
                        "url": src_url,
                        "dom_elements_json": json.dumps(chunk, ensure_ascii=False),
                    })
                    llm_call_count += 1
                    feats = result.get("features", [])
                    for feat in feats:
                        feat["screenshot_file"] = screenshot
                        feat["source_url"]      = src_url   # URL별 캐시용
                        feat["scope"]           = scope     # "global" | "page"
                    all_features.extend(feats)
                    count += len(feats)
                    success = True
                    break
                except Exception as e:
                    llm_error_count += 1
                    if attempt < _CHUNK_MAX_RETRY:
                        _cb(f"  ⚠ DOM_SPEC 오류 재시도 "
                            f"({attempt}/{_CHUNK_MAX_RETRY}): {e}")
                    else:
                        _cb(f"  ✗ DOM_SPEC 최종 실패 "
                            f"({label} 청크 {chunk_idx}/{len(chunks)}): {e}")
            if not success:
                _cb(f"  {label} 청크 {chunk_idx} 건너뜀")
        return count

    # 전역 컴포넌트 판정 + 페이지별 요소에서 제거
    global_report: dict = {"enabled": False}
    global_elements: dict = {}   # sig → 대표 요소 1개
    if dedup_global_components and page_specs:
        global_sigs, global_report = _detect_global_components(
            [ps["elements"] for ps in page_specs], global_ratio, min_pages_for_global
        )
        if global_sigs:
            for ps in page_specs:
                kept = []
                for el in ps["elements"]:
                    sig = _element_signature(el)
                    if sig is not None and sig in global_sigs:
                        global_elements.setdefault(sig, el)  # 첫 등장만 보존(이동)
                    else:
                        kept.append(el)
                ps["elements"] = kept
            global_report["global_elements_extracted"] = len(global_elements)
            _cb(f"🌐 전역 컴포넌트 {len(global_elements)}종 감지 "
                f"(≥{global_report['threshold_pages']}/{global_report['total_pages']} 페이지 공통) "
                f"→ 1회만 명세")

    # ── 네비게이션 링크 축약 (아이디어 1) ────────────────────────────────────
    nav_dropped_total = 0
    nav_samples: list[str] = []

    # 전역 컴포넌트 먼저 명세 (1회)
    if global_elements:
        gv = list(global_elements.values())
        if collapse_nav_links:
            gv, gdrop, gsamp = _collapse_nav_links(gv, nav_link_keep)
            if gdrop:
                nav_dropped_total += gdrop
                nav_samples.extend(gsamp)
                _cb(f"  🧭 전역 네비게이션 링크 {gdrop}개 축약 (대표 {nav_link_keep}개 유지)")
        gc = _spec_elements(gv, "__global__", "", "global", "전역")
        _cb(f"  전역 컴포넌트 기능 {gc}개 추출")

    # 페이지별(전역 제거됨) 명세
    for i, ps in enumerate(page_specs, 1):
        if should_stop and should_stop():
            _cb("⏹ 사용자 중단 — DOM_SPEC 종료")
            break
        if not ps["elements"]:
            continue
        els = ps["elements"]
        if collapse_nav_links:
            els, pdrop, psamp = _collapse_nav_links(els, nav_link_keep)
            if pdrop:
                nav_dropped_total += pdrop
                if len(nav_samples) < 10:
                    nav_samples.extend(psamp[: 10 - len(nav_samples)])
        _cb(f"명세 중 ({i}/{len(page_specs)}): {ps['url']} — 요소 {len(els)}개")
        pc = _spec_elements(els, ps["url"], ps["screenshot"], "page", ps["url"])
        _cb(f"  페이지 기능 {pc}개 추출")

    nav_collapse_report = {
        "enabled":        bool(collapse_nav_links),
        "keep_per_group": nav_link_keep,
        "dropped":        nav_dropped_total,
        "dropped_samples": nav_samples[:10],
    }
    if nav_dropped_total:
        _cb(f"🧭 네비게이션 링크 축약 완료 — 총 {nav_dropped_total}개 대표로 압축")

    # ── feature 스키마 정규화 ────────────────────────────────────────────────
    # LLM이 category_mid 등을 누락하거나, 구버전 캐시 draft가 다른 스키마일 때
    # 이후 단계(markdown 요약·Stage 1 leaf 추출)가 KeyError로 죽지 않도록 보강.
    for f in all_features:
        if not f.get("category_major"):
            f["category_major"] = "기타"
        if not f.get("category_mid"):
            f["category_mid"] = "일반"
        if not f.get("category_leaf"):
            f["category_leaf"] = f.get("implicit_spec") or "미분류"
        f.setdefault("implicit_spec", "")
        f.setdefault("source_element", "")
        f.setdefault("confidence", "")
        f.setdefault("screenshot_file", "")
        f.setdefault("scope", "page")   # 캐시 passthrough feature는 scope 없음 → page

    # ── 명세 초안 저장 ────────────────────────────────────────────────────────
    draft = {
        "url":           url,
        "pages_scanned": len(visited),
        "features":      all_features,
        "llm_calls":     llm_call_count,
        "llm_errors":    llm_error_count,
        "cache_hits":    cache_hit_count,
        "global_component_report": global_report,   # D51 전역 dedup 결과
        "nav_collapse_report":     nav_collapse_report,  # 아이디어 1 네비 링크 축약 결과
    }
    spec_path = out_dir / "feature-spec-draft.json"
    spec_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")

    # 마크다운도 생성 (정규화 후이므로 .get으로도 안전)
    md_lines = [
        f"# 기능 명세 초안\n\n"
        f"> URL: {url}  |  스캔 페이지: {len(visited)}  |  기능 추출: {len(all_features)}개\n"
    ]
    for f in all_features:
        md_lines.append(
            f"## {f.get('category_major','기타')} > {f.get('category_mid','일반')} > {f.get('category_leaf','미분류')}\n"
            f"- 명세: {f.get('implicit_spec','')}\n"
            f"- 근거 요소: `{f.get('source_element','')}`  신뢰도: {f.get('confidence','')}\n"
            f"- 스크린샷: {f.get('screenshot_file','')}\n"
        )
    (out_dir / "feature-spec-draft.md").write_text("\n".join(md_lines), encoding="utf-8")

    _cb(f"Stage 0 완료 - 기능 {len(all_features)}개 추출 "
        f"(LLM 호출 {llm_call_count}회, 오류 {llm_error_count}회)")

    # ── features 0개 → 진행 불가 ─────────────────────────────────────────────
    if not all_features:
        err_parts = [
            "Stage 0: 기능 목록이 0개입니다. Stage 1로 진행할 수 없습니다.",
            "",
            f"  - 스캔 페이지: {len(visited)}개",
            f"  - LLM 호출 시도: {llm_call_count}회 성공 / {llm_error_count}회 실패",
            "",
            "가능한 원인:",
        ]
        if llm_error_count > 0 and llm_call_count == 0:
            err_parts += [
                "  [LLM API 오류] API 키가 잘못됐거나 네트워크가 LLM 서버를 차단 중입니다.",
                "  → 대시보드 설정 탭에서 API 키를 확인하세요.",
            ]
        elif llm_call_count > 0:
            err_parts += [
                "  [LLM 응답 미흡] LLM이 기능을 추출하지 못했습니다.",
                "  → 대상 페이지의 DOM 구조가 너무 단순하거나 로그인 등 인증이 필요할 수 있습니다.",
            ]
        else:
            err_parts += [
                "  [DOM 요소 없음] 스캔된 모든 페이지에서 인터랙티브 요소를 찾지 못했습니다.",
            ]
        raise RuntimeError("\n".join(err_parts))

    return draft
