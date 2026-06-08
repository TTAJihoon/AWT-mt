"""Stage 1 — 입력 파일 파싱·정규화 → leaf 목록 추출."""
from __future__ import annotations
import re
from pathlib import Path
from typing import Callable

from app.tools.file_parser import parse
from app.core.taxonomy import classify_major, TAXONOMY_VERSION


def ingest(
    files: list[str | Path],
    run_dir: Path,
    feature_spec: dict | None = None,
    progress_cb: Callable[[str], None] | None = None,
) -> dict:
    """파일 목록을 파싱해 매뉴얼 텍스트와 leaf 목록을 반환.

    Returns:
        {
            "manual_text": str,
            "leaves": [{"requirement_id": str, "category_major": str,
                        "category_mid": str, "category_leaf": str}],
        }
    """
    def _cb(msg: str):
        if progress_cb:
            progress_cb(msg)

    out_dir = run_dir / "ingest"
    out_dir.mkdir(parents=True, exist_ok=True)

    texts: list[str] = []
    for f in files:
        _cb(f"파싱 중: {Path(f).name}")
        texts.append(parse(f))

    manual_text = "\n\n".join(texts)
    (out_dir / "manual.txt").write_text(manual_text, encoding="utf-8")

    # leaf 목록 구성
    leaves: list[dict] = []
    refine_report: dict = {}

    # Stage 0 결과 있으면 우선 사용
    if feature_spec and feature_spec.get("features"):
        feats = feature_spec["features"]
        raw_leaves = []
        for feat in feats:
            raw_leaves.append({
                "category_major":  feat.get("category_major", ""),
                "category_mid":    feat.get("category_mid", ""),
                "category_leaf":   feat.get("category_leaf", ""),
                "screenshot_file": feat.get("screenshot_file", ""),
                "confidence":      feat.get("confidence", ""),
                "source_url":      feat.get("source_url", ""),
            })
        # ── leaf 정제: 노이즈 제거 + 중복 병합 (커버리지 품질 향상) ──────────
        leaves, refine_report = _refine_leaves(raw_leaves)
        # requirement_id 재부여
        for i, lf in enumerate(leaves, 1):
            lf["requirement_id"] = f"F{i:03d}"
        if refine_report.get("removed_noise") or refine_report.get("merged_dup"):
            _cb(
                f"기능 정제 — 원본 {refine_report['original']}개 → "
                f"노이즈 {refine_report['removed_noise']}개 제외 + "
                f"중복 {refine_report['merged_dup']}개 병합 → "
                f"고유 기능 {refine_report['final']}개"
            )

        # 매뉴얼 파일이 없는 경우 implicit_spec을 manual_text로 합성
        # → Stage 2 TC_DESIGN이 참조할 텍스트 컨텍스트 확보
        if not manual_text.strip():
            spec_lines = [
                f"# {feature_spec.get('url', 'DOM 스캔 결과')}\n",
                f"스캔 페이지 수: {feature_spec.get('pages_scanned', '?')}\n",
            ]
            for feat in feats:
                maj = feat.get("category_major", "")
                mid = feat.get("category_mid", "")
                lef = feat.get("category_leaf", "")
                spec = feat.get("implicit_spec", "")
                src  = feat.get("source_element", "")
                spec_lines.append(
                    f"\n## {maj}\n### {mid} — {lef}\n{spec}\n"
                    f"(근거 요소: {src}  신뢰도: {feat.get('confidence','')})\n"
                )
            manual_text = "\n".join(spec_lines)
            _cb(f"  매뉴얼 없음 → DOM implicit_spec {len(feats)}개를 참조문서로 합성")
    else:
        # 파일에서 기능 목록 추출 (마크다운 헤더 기반 휴리스틱)
        leaves = _extract_leaves_from_text(manual_text)

    _cb(f"Stage 1 완료 - leaf {len(leaves)}개")
    return {"manual_text": manual_text, "leaves": leaves, "refine_report": refine_report}


# ── leaf 정제 (노이즈 제거 + 중복 병합) ───────────────────────────────────────
# 시험 가치가 낮은 순수 UI 동작 — 기능명에 이 패턴이 있으면 제외 (소문자 비교)
_NOISE_LEAF_PATTERNS = (
    "scroll to top", "맨 위로", "위로 가기", "상단 이동", "top 버튼", "back to top",
    "skip to", "skip navigation", "본문 바로가기", "바로가기 링크", "건너뛰기",
    "toggle menu", "open all menu", "toggle all menu", "all menu", "open menu", "close menu",
    "전체 메뉴 열기", "전체메뉴", "전체 메뉴", "메뉴 토글", "메뉴 열기", "메뉴 닫기", "메뉴 펼치기",
    "mobile version", "pc version", "desktop version",
    "모바일 버전", "pc 버전", "데스크탑 버전", "모바일로 보기", "pc로 보기",
    "print", "인쇄하기", "프린트",
)


def _normalize_leaf_name(name: str) -> str:
    """기능명 정규화 — 중복 판정용. 공백·숫자·기호 차이를 흡수."""
    import re
    s = (name or "").strip().lower()
    s = re.sub(r"\s+", " ", s)         # 연속 공백 → 1개
    s = re.sub(r"[#\d]+", "", s)        # 숫자·# 제거 (글7 vs 글6 등)
    s = re.sub(r"[()\[\]{}<>:·•\-_/]+", " ", s).strip()
    return s


def _is_noise_leaf(leaf: dict) -> bool:
    name = (leaf.get("category_leaf", "") or "").lower()
    return any(pat in name for pat in _NOISE_LEAF_PATTERNS)


def _refine_leaves(raw_leaves: list[dict]) -> tuple[list[dict], dict]:
    """노이즈 제거 + 중복 병합 → 고유 기능 leaf만 반환 + 정제 리포트.

    중복 키 = (대분류, 중분류, 정규화된 소분류). 첫 항목 유지, 나머지 병합.
    """
    original = len(raw_leaves)
    removed_noise = 0
    merged_dup = 0
    coerced_major = 0                       # D52 — 통제 어휘로 보정된 leaf 수
    unknown_samples: list[str] = []         # 통제 어휘 밖(원본 유지) 대분류 샘플

    seen: dict[tuple, dict] = {}
    noise_samples: list[str] = []
    for lf in raw_leaves:
        if _is_noise_leaf(lf):
            removed_noise += 1
            if len(noise_samples) < 20:
                noise_samples.append(lf.get("category_leaf", ""))
            continue
        # ── D52: 대분류 통제 어휘 보정 (dedup 키 계산 전에 수행해야
        #         "User Management"/"Authentication"/"Account" 같은 인증 분열이
        #         단일 "회원·인증"으로 합쳐져 실제 중복 병합이 일어난다) ──────────
        raw_major = lf.get("category_major", "") or ""
        # 도메인 우선 분류 — leaf·중분류까지 보아 "폼·입력검증" 등 상호작용 유형이
        # 제품 도메인을 가리지 않게 한다(2축 분리, 아이디어 A).
        canon, status = classify_major(
            raw_major, lf.get("category_mid", ""), lf.get("category_leaf", "")
        )
        if status == "coerced":
            coerced_major += 1
            lf["category_major_raw"] = raw_major   # 추적성
        elif status == "unknown" and len(unknown_samples) < 30:
            unknown_samples.append(raw_major)
        lf["category_major"] = canon
        key = (
            (lf.get("category_major", "") or "").strip().lower(),
            (lf.get("category_mid", "") or "").strip().lower(),
            _normalize_leaf_name(lf.get("category_leaf", "")),
        )
        if key in seen:
            merged_dup += 1
            # 병합된 출처 URL 누적 (추적성)
            src = lf.get("source_url", "")
            if src:
                seen[key].setdefault("merged_sources", [])
                if src not in seen[key]["merged_sources"]:
                    seen[key]["merged_sources"].append(src)
        else:
            seen[key] = dict(lf)

    leaves = list(seen.values())
    report = {
        "original":         original,
        "removed_noise":    removed_noise,
        "merged_dup":       merged_dup,
        "final":            len(leaves),
        "noise_samples":    noise_samples,
        # D52 — 통제 어휘 보정 결과
        "taxonomy_version":     TAXONOMY_VERSION,
        "coerced_major":        coerced_major,
        "unknown_major_samples": unknown_samples,
    }
    return leaves, report


def _extract_leaves_from_text(text: str) -> list[dict]:
    """마크다운/텍스트에서 계층형 기능 목록 추출 (휴리스틱).

    헤딩 레벨 자동 보정(off-by-one 방지):
        일반 매뉴얼은 `#`=대분류 / `##`=중분류 / `###`=소분류로 가정한다.
        그러나 "# 문서제목 / ## 도메인 / ### 기능" 구조(최상위 `#`이 문서 제목
        하나뿐)에서는 모든 기능이 같은 대분류(문서 제목)로 뭉쳐 제품 도메인이
        사라진다. → `#`이 1개뿐이고 `##`이 2개 이상이면 레벨을 한 칸 승격해
        `##`을 대분류로, `###`을 소분류로 사용한다(중분류는 대분류와 동일).
    """
    lines = text.splitlines()
    n_h1 = sum(1 for l in lines if l.strip().startswith("# "))
    n_h2 = sum(1 for l in lines if l.strip().startswith("## "))
    shift = (n_h1 <= 1 and n_h2 >= 2)

    leaves: list[dict] = []
    h1 = h2 = ""
    idx = 0

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### "):
            leaf = stripped[4:].strip()
            if shift:
                major, mid = h2, h2     # ## → 대분류(+중분류)
            else:
                major, mid = h1, h2     # 기존 3-레벨 매핑
            if major and mid and leaf:
                idx += 1
                leaves.append({
                    "requirement_id": f"F{idx:03d}",
                    "category_major": major,
                    "category_mid": mid,
                    "category_leaf": leaf,
                })
        elif stripped.startswith("## "):
            h2 = stripped[3:].strip()
        elif stripped.startswith("# "):
            h1 = stripped[2:].strip()
            h2 = ""

    # 헤더가 없으면 섹션 전체를 leaf 1개로
    if not leaves and text.strip():
        leaves.append({
            "requirement_id": "F001",
            "category_major": "전체 기능",
            "category_mid": "일반",
            "category_leaf": "기능 전체",
        })
    return leaves


def excerpt_for_leaf(manual_text: str, leaf: dict, max_chars: int = 1500) -> str:
    """매뉴얼에서 해당 leaf 관련 섹션 발췌 (V2 근거 확보)."""
    keyword = leaf.get("category_leaf", "") or leaf.get("category_mid", "")
    if not keyword:
        return manual_text[:max_chars]

    idx = manual_text.find(keyword)
    if idx == -1:
        return manual_text[:max_chars]

    start = max(0, idx - 200)
    end = min(len(manual_text), idx + max_chars - 200)
    return manual_text[start:end]
