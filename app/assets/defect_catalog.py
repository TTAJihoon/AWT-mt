"""결함 카탈로그 CRUD + 유사 결함 검색 + 이벤트 로깅."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.auth.db_client import DBClient

_ASSETS_DIR = Path(__file__).parent.parent.parent / "data" / "assets"
_CATALOG_DIR = _ASSETS_DIR / "defect-catalog"

_PRODUCT_TYPE_ABBR: dict[str, str] = {
    "BOARD_CMS":     "BRD",
    "USER_AUTH":     "USR",
    "SHOPPING":      "SHP",
    "SEARCH":        "SRC",
    "DASHBOARD":     "DSH",
    "FORM_WORKFLOW": "FRM",
    "OTHER":         "OTH",
}


def next_defect_id(product_type_id: str) -> str:
    """다음 결함 ID 생성: DEF-YYYY-TYPE-NNN."""
    abbr = _PRODUCT_TYPE_ABBR.get(product_type_id, "OTH")
    year = datetime.now(timezone.utc).year
    target_dir = _CATALOG_DIR / product_type_id
    target_dir.mkdir(parents=True, exist_ok=True)
    max_num = 0
    for f in target_dir.glob(f"DEF-{year}-{abbr}-*.json"):
        try:
            max_num = max(max_num, int(f.stem.split("-")[-1]))
        except (ValueError, IndexError):
            pass
    return f"DEF-{year}-{abbr}-{max_num + 1:03d}"


# ── 파일 CRUD ────────────────────────────────────────────────────────────────

def load_defect(defect_id: str, product_type_id: str) -> dict | None:
    path = _CATALOG_DIR / product_type_id / f"{defect_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_defect(defect: dict, actor_username: str, db: "DBClient | None" = None) -> None:
    """결함 저장 + _meta 업데이트 + DB 이벤트 로깅."""
    product_type_id = defect["product"]["productTypeId"]
    target_dir = _CATALOG_DIR / product_type_id
    target_dir.mkdir(parents=True, exist_ok=True)

    now_iso = datetime.now(timezone.utc).isoformat()
    if "_meta" not in defect:
        defect["_meta"] = {}
    meta = defect["_meta"]
    if "createdBy" not in meta:
        meta["createdBy"] = actor_username
        meta["createdAt"] = now_iso
    meta["lastModifiedBy"] = actor_username
    meta["lastModifiedAt"] = now_iso

    path = target_dir / f"{defect['defectId']}.json"
    path.write_text(json.dumps(defect, ensure_ascii=False, indent=2), encoding="utf-8")

    if db:
        _log_event(db, "defect", defect["defectId"], "created", actor_username)


def approve_pattern(
    defect_id: str,
    product_type_id: str,
    actor_username: str,
    db: "DBClient | None" = None,
) -> bool:
    """patternProposal 승인 처리."""
    defect = load_defect(defect_id, product_type_id)
    if not defect:
        return False
    proposal = (defect.get("learning") or {}).get("patternProposal")
    if not proposal:
        return False

    proposal["status"] = "approved"
    now_iso = datetime.now(timezone.utc).isoformat()
    defect["_meta"]["patternApprovedBy"] = actor_username
    defect["_meta"]["patternApprovedAt"] = now_iso

    path = _CATALOG_DIR / product_type_id / f"{defect_id}.json"
    path.write_text(json.dumps(defect, ensure_ascii=False, indent=2), encoding="utf-8")

    if db:
        _log_event(db, "defect", defect_id, "pattern_approved", actor_username)
    return True


def list_defects(product_type_id: str | None = None) -> list[dict]:
    """결함 목록 반환. product_type_id 미지정 시 전체."""
    dirs = [_CATALOG_DIR / product_type_id] if product_type_id else [
        d for d in _CATALOG_DIR.iterdir() if d.is_dir()
    ]
    result: list[dict] = []
    for d in dirs:
        for f in sorted(d.glob("DEF-*.json")):
            try:
                result.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
    return result


def search_similar_defects(
    product_type_ids: list[str],
    feature_type: str,
    top_k: int = 3,
) -> list[dict]:
    """유사 결함 검색 (Phase 1: featureType 키워드 매칭).

    Phase 2+에서 벡터 임베딩 RAG로 교체 예정.
    """
    candidates: list[dict] = []
    for ptype in product_type_ids:
        for defect in list_defects(ptype):
            if (defect.get("feature") or {}).get("featureType") == feature_type:
                candidates.append(defect)
            else:
                learning = defect.get("learning") or {}
                pattern = learning.get("patternProposal") or {}
                if pattern.get("status") == "approved":
                    applies_to = pattern.get("appliesTo") or []
                    if feature_type in applies_to:
                        candidates.append(defect)

    # 중복 제거 (defectId 기준)
    seen: set[str] = set()
    unique: list[dict] = []
    for d in candidates:
        if d["defectId"] not in seen:
            seen.add(d["defectId"])
            unique.append(d)

    return unique[:top_k]


def format_for_llm(defects: list[dict], max_chars: int = 1500) -> str:
    """LLM 입력용 유사 결함 요약 텍스트.

    source_quote 3단계 중 'defect:DEF-ID' 출처 근거.
    """
    if not defects:
        return ""
    lines: list[str] = []
    for d in defects:
        proposal = (d.get("learning") or {}).get("patternProposal") or {}
        checks = proposal.get("checks", [])
        lines.append(f"[{d['defectId']}] {d['title']}")
        lines.append(f"  현상: {d['observedBehavior']}")
        lines.append(f"  기대: {d['expectedBehavior']}")
        if checks:
            lines.append(f"  검증: {' / '.join(checks[:2])}")
        lines.append("")

    text = "\n".join(lines).strip()
    return text[:max_chars] if len(text) > max_chars else text


# ── DB 이벤트 로깅 ────────────────────────────────────────────────────────────

def _log_event(
    db: "DBClient",
    asset_type: str,
    asset_id: str,
    action: str,
    actor_name: str,
    note: str = "",
) -> None:
    try:
        with db._cur() as cur:
            cur.execute(
                "SELECT user_id FROM awt_users WHERE username=%s",
                (actor_name,),
            )
            row = cur.fetchone()
            actor_id = row["user_id"] if row else None
            cur.execute(
                "INSERT INTO awt_asset_events "
                "(asset_type, asset_id, action, actor_id, actor_name, note) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (asset_type, asset_id, action, actor_id, actor_name, note),
            )
        db._conn.commit()
    except Exception:
        pass  # 이벤트 로깅 실패는 메인 흐름을 막지 않음
