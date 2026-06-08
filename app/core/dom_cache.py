"""과거 run에서 URL별 DOM_SPEC 캐시 조회.

같은 target_url을 가진 가장 최근 run에서 URL 일치하는 features를 가져온다.
"""
from __future__ import annotations
import json
from pathlib import Path

_RUNS_DIR = Path("data/runs")


def find_recent_run_for_url(
    target_url: str,
    exclude_run_id: str | None = None,
) -> Path | None:
    """같은 target_url을 가진 가장 최근 run 디렉토리 경로 반환.

    Args:
        target_url:    찾을 시작 URL
        exclude_run_id: 현재 진행 중인 run은 제외 (자기 자신 캐시 방지)

    Returns:
        가장 최근(mtime 기준) feature-spec-draft.json이 존재하는 run 경로. 없으면 None.
    """
    if not _RUNS_DIR.exists():
        return None

    candidates: list[tuple[float, Path]] = []
    for run_dir in _RUNS_DIR.iterdir():
        if not run_dir.is_dir():
            continue
        if exclude_run_id and run_dir.name == exclude_run_id:
            continue

        draft_path = run_dir / "dom-scan" / "feature-spec-draft.json"
        if not draft_path.exists():
            continue
        try:
            draft = json.loads(draft_path.read_text(encoding="utf-8"))
            if draft.get("url") == target_url and draft.get("features"):
                candidates.append((draft_path.stat().st_mtime, run_dir))
        except Exception:
            continue

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def extract_cached_features_by_url(
    run_dir: Path,
    page_urls: list[str],
) -> dict[str, list[dict]]:
    """run의 feature-spec-draft.json에서 page_urls와 일치하는 features를 URL별로 묶어 반환.

    구버전 draft(feature에 source_url 필드 없음)는 매칭 불가 → 빈 결과.
    """
    draft_path = run_dir / "dom-scan" / "feature-spec-draft.json"
    if not draft_path.exists():
        return {}

    try:
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    features = draft.get("features") or []
    wanted   = set(page_urls)
    grouped: dict[str, list[dict]] = {}
    for feat in features:
        src = feat.get("source_url")
        if src and src in wanted:
            grouped.setdefault(src, []).append(feat)
    return grouped


def cache_status_for_urls(
    target_url: str,
    page_urls: list[str],
    exclude_run_id: str | None = None,
) -> tuple[dict[str, list[dict]], Path | None]:
    """target_url의 최근 run에서 page_urls 각각 캐시 features 조회.

    Returns:
        (캐시맵, 원본 run 경로)
        — 캐시맵: {url: [features...]} (캐시 있는 URL만 포함)
        — run 경로: 캐시 출처 run의 경로 (없으면 None)
    """
    run_dir = find_recent_run_for_url(target_url, exclude_run_id=exclude_run_id)
    if run_dir is None:
        return {}, None
    return extract_cached_features_by_url(run_dir, page_urls), run_dir
