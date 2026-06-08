"""Stage 0 사전 단계 — URL 목록만 빠르게 BFS 수집 (LLM·스크린샷 X).

페이지 선택 다이얼로그용 데이터를 수집한다.
DOM 분석/스크린샷은 stage0_dom_scan.py에서 별도로 수행.
"""
from __future__ import annotations
from typing import Callable
from playwright.sync_api import sync_playwright


def collect_urls(
    start_url: str,
    max_pages: int = 500,                            # 안전 상한 (사이트 폭발 방지)
    max_depth: int = 2,
    auth_sequence: list[dict] | None = None,
    progress_cb: Callable[[str], None] | None = None,
    should_stop: Callable[[], bool] | None = None,   # 사용자 중단 신호 (협력적)
) -> list[dict]:
    """시작 URL에서 BFS로 같은 origin 페이지를 수집.

    Args:
        max_pages:   안전 상한. 일반적으로 BFS는 자연 종료(같은 origin 링크 소진).
        should_stop: True를 반환하면 BFS 즉시 중단 (협력적 인터럽트).

    Returns:
        [{"url", "title", "depth", "fingerprint", "group_key",
          "is_representative", "group_size", "group_rep_url"}, ...]
        — 발견 순서대로. start_url이 첫 항목.
        · fingerprint:      DOM 구조 골격 해시 (L2)
        · group_key:        (식별 URL, fingerprint) 조합 키
        · is_representative: 그룹 대표 페이지면 True (분석 대상)
        · group_size:       이 그룹에 묶인 동형 페이지 수
        · group_rep_url:    이 페이지가 속한 그룹의 대표 URL
    """
    def _cb(msg: str) -> None:
        if progress_cb:
            progress_cb(msg)

    def _stopped() -> bool:
        return bool(should_stop and should_stop())

    collected: list[dict] = []
    visited: set[str] = set()
    base_origin = _origin(start_url)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page    = context.new_page()

        _cb(f"URL 수집 시작: {start_url}")
        try:
            page.goto(start_url, wait_until="networkidle", timeout=30000)
        except Exception as e:
            _cb(f"⚠ 시작 URL 접근 실패: {e}")
            browser.close()
            return collected

        # 인증 시퀀스 (필요 시)
        if auth_sequence:
            for step in auth_sequence:
                action = step.get("action")
                try:
                    if action == "fill":
                        page.fill(step["selector"], step["value"])
                    elif action == "click":
                        page.click(step["selector"])
                        page.wait_for_load_state("networkidle", timeout=10000)
                    elif action == "goto":
                        page.goto(step.get("url", step.get("selector", "")),
                                  wait_until="networkidle", timeout=20000)
                except Exception as e:
                    _cb(f"⚠ 인증 단계 실패 (무시): {e}")
            _cb("인증 완료")

        # BFS — 시작 URL도 정규화해 끝슬래시/index 차이로 인한 중복 방지
        queue: list[tuple[str, int]] = [(_canonical(start_url) or start_url, 0)]
        stopped_by_user = False
        while queue and len(collected) < max_pages:
            # 사용자 중단 협력 체크
            if _stopped():
                stopped_by_user = True
                _cb("⏹ 사용자 중단 — BFS 종료")
                break

            cur_url, depth = queue.pop(0)
            if cur_url in visited:
                continue
            visited.add(cur_url)

            try:
                if cur_url != page.url:
                    page.goto(cur_url, wait_until="networkidle", timeout=20000)

                title = (page.title() or "").strip() or "(제목 없음)"
                # L2: DOM 구조 골격 추출 → 지문(해시). 텍스트·값은 제외하고
                #     태그+type+name 골격만 → 같은 템플릿 페이지는 같은 지문
                try:
                    skeleton = page.evaluate(_SKELETON_JS)
                except Exception:
                    skeleton = ""
                fp = _fingerprint(skeleton)
                collected.append({
                    "url":         cur_url,
                    "title":       title[:80],
                    "depth":       depth,
                    "fingerprint": fp,
                })
                _cb(f"   ({len(collected)}) {title[:40]}  ←  {cur_url}")

                # 같은 origin 링크 수집 (depth + 1)
                if depth < max_depth:
                    links = page.evaluate(
                        "() => [...document.querySelectorAll('a[href]')].map(a=>a.href)"
                    )
                    seen_in_queue = {u for u, _ in queue} | visited
                    for lnk in links:
                        # query string과 fragment 제거 — 동일 페이지의 변형 URL 중복 방지
                        canon = _canonical(lnk)
                        if not canon:
                            continue
                        # 같은 origin & 아직 방문 안 함 & queue에도 없음
                        if (_origin(canon) == base_origin
                                and canon not in seen_in_queue):
                            queue.append((canon, depth + 1))
                            seen_in_queue.add(canon)
            except Exception as e:
                _cb(f"   ⚠ 페이지 스킵 ({cur_url}): {e}")

        browser.close()

    # ── L1+L2 그룹핑: (식별 URL, 구조 지문)으로 동형 페이지 묶기 ──────────
    _assign_groups(collected)
    n_total = len(collected)
    n_groups = len({e["group_key"] for e in collected}) if collected else 0
    n_dup = n_total - n_groups

    if stopped_by_user:
        _cb(f"URL 수집 중단 — {n_total}개까지 수집")
    elif n_total >= max_pages:
        _cb(f"URL 수집 한도 도달 ({max_pages}) — {n_total}개")
    else:
        _cb(f"URL 수집 완료 — {n_total}개 발견 (사이트 BFS 자연 종료)")
    if n_dup > 0:
        _cb(
            f"🧹 중복 정리 — {n_total}개 중 고유 기능 {n_groups}개 "
            f"(동형/변형 {n_dup}개는 대표로 묶음)"
        )
    return collected


# ── L1: URL 노이즈 파라미터 (값이 달라도 같은 페이지 유형) ────────────────────
# 이 파라미터들은 페이지 '정체성'을 바꾸지 않으므로 식별 URL에서 제거한다.
#   - 페이지네이션·검색·정렬·디바이스·리다이렉트·캐시버스터
# 반대로 bo_table/co_id/type/w/mode 등 '페이지 유형'을 가르는 파라미터는 보존.
_NOISE_PARAMS = {
    # 페이지네이션
    "page", "pg", "p",
    # 개별 레코드 ID (구조 지문이 목록 vs 상세를 구분하므로 안전)
    "wr_id", "no", "idx", "seq",
    # 검색·정렬 (gnuboard5 + 일반)
    "sop", "sst", "sfl", "stx", "sca", "spt", "sword", "sort", "order", "q",
    # 리다이렉트 대상
    "url", "rurl", "redirect", "return", "returnurl", "ref", "next",
    # 디바이스·캐시버스터
    "device", "_", "t", "ts", "timestamp", "rnd", "v",
}

# L2: 구조 골격 추출 JS (텍스트·값 제외, 골격만)
_SKELETON_JS = r"""
() => {
    const tags = ['form','input','select','textarea','button','a','table',
                  'ul','ol','nav','h1','h2','h3','section','article','fieldset'];
    const parts = [];
    for (const el of document.querySelectorAll(tags.join(','))) {
        let t = el.tagName.toLowerCase();
        const ty = el.getAttribute('type');
        if (ty) t += ':' + ty;
        const nm = el.getAttribute('name');
        if (nm) t += '#' + nm.replace(/\d+/g, 'N');  // 숫자 인덱스는 N으로 일반화
        parts.push(t);
    }
    return parts.join(',');
}
"""


def _fingerprint(skeleton: str) -> str:
    """구조 골격 문자열 → 짧은 해시. 빈 골격은 'empty'."""
    import hashlib
    s = (skeleton or "").strip()
    if not s:
        return "empty"
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:12]


def _identity_url(url: str) -> str:
    """노이즈 파라미터를 제거한 '식별 URL' (L1).

    같은 식별 URL + 같은 구조 지문 = 동형 페이지 그룹.
    """
    from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
    try:
        u = urlparse(_canonical(url) or url)
        if u.query:
            kept = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
                    if k.lower() not in _NOISE_PARAMS]
            query = urlencode(sorted(kept))   # 정렬 → 파라미터 순서 무관
        else:
            query = ""
        return urlunparse((u.scheme, u.netloc, u.path, u.params, query, ""))
    except Exception:
        return url


def _assign_groups(entries: list[dict]) -> None:
    """entries에 group_key/is_representative/group_size/group_rep_url을 채운다.

    그룹 키 = (식별 URL, 구조 지문).
      - 같은 게시판 글들(wr_id 차이)은 식별 URL·지문 동일 → 한 그룹
      - 게시판 목록 vs 글보기는 지문이 달라 → 다른 그룹
      - free/qa 게시판은 식별 URL(bo_table)이 달라 → 다른 그룹
    각 그룹의 대표 = URL이 가장 짧은 항목(보통 가장 기본형).
    """
    groups: dict[tuple, list[dict]] = {}
    for e in entries:
        key = (_identity_url(e["url"]), e.get("fingerprint", "empty"))
        e["group_key"] = repr(key)
        groups.setdefault(e["group_key"], []).append(e)

    for key, members in groups.items():
        # 대표 선정: URL이 가장 짧은(=가장 기본형) 항목
        rep = min(members, key=lambda m: len(m["url"]))
        for m in members:
            m["group_size"]       = len(members)
            m["group_rep_url"]    = rep["url"]
            m["is_representative"] = (m is rep)


_INDEX_FILES = ("index.php", "index.html", "index.htm", "default.php", "default.aspx")


def _canonical(url: str) -> str:
    """URL을 정규화해 '같은 페이지의 다른 표기'로 인한 중복을 제거.

    정규화 규칙:
      - fragment(#anchor) 제거 — 같은 페이지의 다른 위치
      - 끝 슬래시 제거 — '/page' 와 '/page/' 동일 취급 (단, 루트는 '/' 유지)
      - index 파일 제거 — '/dir/index.php' → '/dir' (루트는 '/' 유지)
      - query string은 보존 — board.php?bo_table=free 와 ?bo_table=qa 는
        서로 다른 페이지이므로 합치지 않음 (게시판 구분 등)
    """
    from urllib.parse import urlparse, urlunparse
    try:
        u = urlparse(url)
        if not u.scheme or not u.netloc:
            return ""
        path = u.path or "/"
        # index 파일 제거 (query가 없을 때만 — index.php?action=x 는 의미 있을 수 있음)
        if not u.query:
            for idx in _INDEX_FILES:
                if path.lower().endswith("/" + idx):
                    path = path[: -len(idx)]   # '/dir/index.php' → '/dir/'
                    break
        # 끝 슬래시 제거 (루트 제외)
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")
        if not path:
            path = "/"
        return urlunparse((u.scheme, u.netloc, path, u.params, u.query, ""))
    except Exception:
        return url


def _origin(url: str) -> str:
    """URL의 origin(스킴 + 호스트 + 포트) 추출."""
    from urllib.parse import urlparse
    try:
        u = urlparse(url)
        return f"{u.scheme}://{u.netloc}"
    except Exception:
        return ""
