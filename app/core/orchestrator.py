"""Stage 0~7 파이프라인 흐름 제어 (D43)."""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from app.api.llm_client import LLMClient
from app.core import (
    stage1_ingest,
    stage1b_consolidate,
    stage2_tc_design,
    stage3_verify,
    stage6_enhance,
    stage6b_defect_feedback,
    stage7_output,
)
# stage0_dom_scan / stage5_execute는 web 어댑터가 lazy import (playwright 비의존화)
from app.tools.excel_builder import build_review

RUNS_DIR = Path("data/runs")


@dataclass
class RunConfig:
    api_key: str
    target_url: str
    input_files: list[str] = field(default_factory=list)
    auth_sequence: list[dict] = field(default_factory=list)
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    inferred_threshold: float = 0.30
    max_leaves: int = 50
    """Stage 2에서 처리할 최대 leaf 수. 0 = 무제한.
    무료 플랜(20회/일) 기준: 50이면 약 50회 TC_DESIGN 호출 필요.
    유료 플랜이면 0으로 설정해 제한 없이 실행."""
    model_override: str | None = None
    """Contract frontmatter 모델을 이 모델로 교체 (전역 기본). 예: 'gemini-2.5-flash'.
    None이면 각 Contract의 model 그대로 사용."""

    model_overrides: dict[str, str] | None = None
    """단계(contract_id)별 모델 지정. 예: {'DOM_SPEC':'gpt-5.4-nano', 'TC_DESIGN':'gpt-5.4'}.
    우선순위: model_overrides[contract] > model_override > contract 기본."""

    selected_urls: list[str] | None = None
    """페이지 선택 다이얼로그에서 선택된 URL 목록. None이면 BFS 전체."""

    cached_features: dict[str, list[dict]] | None = None
    """URL → features 캐시 (과거 run에서 복사). 해당 URL은 LLM 호출 생략."""

    selected_url_groups: dict[str, list[str]] | None = None
    """대표 URL → 묶인 동형 URL 목록 (중복 정리 추적성, meta.json 기록용)."""

    consolidate_features: bool = True
    """Stage 1 후 LLM으로 의미 기준 기능 통합(중복 병합) 수행 여부.
    DOM 스캔이 전역 컴포넌트를 페이지마다 재추출하는 중복을 줄임."""

    max_pages: int = 30
    """BFS 최대 페이지 수 (selected_urls가 있으면 무시됨)."""

    headless_exec: bool = True
    """Stage 5 TC 실행 시 헤드리스 여부. False면 별도 Chromium 창이 떠
    사용자가 자동화 동작을 볼 수 있음 (마우스/키보드는 자동화에만 반응)."""

    slow_mo_ms: int = 0
    """Stage 5에서 액션 사이 인공 지연(ms). 헤드풀 모드에서 천천히 보기 위함."""

    dedup_global_components: bool = True
    """Stage 0 — 헤더·푸터·네비처럼 여러 페이지 공통 요소를 전역 컴포넌트로 1회만
    명세(D51). GnuBoard5 헤더 로그인 박스가 페이지마다 중복 추출되어 인증 도메인이
    과대표집되던 문제 해소. False면 기존 동작(페이지마다 전부 명세)."""

    global_ratio: float = 0.4
    """전역 컴포넌트 판정 임계 — 이 비율 이상 페이지에 동일 셀렉터로 등장하면 전역.
    실측: 로그인 폼이 49.4% 페이지에 등장 → 0.5면 놓침. 0.4로 잡되 고유 콘텐츠는 안전."""

    collapse_nav_links: bool = True
    """Stage 0 — nav/header/footer/메뉴 컨테이너 내 '순수 이동 링크'를 대표 N개로 축약.
    네비게이션·메뉴 도메인이 수백 개로 비대해지던 문제(실측 257개/23.8%) 해소.
    로그인·장바구니·결제·검색 등 중요 액션 링크는 보존. False면 모든 링크 명세(기존 동작)."""

    nav_link_keep: int = 8
    """축약 시 element 묶음당 유지할 대표 네비게이션 링크 수."""

    auto_pages: bool = True
    """True(기본)면 실행 시 페이지 선택 다이얼로그·재사용 프롬프트를 생략하고
    자동으로 새 BFS 스캔을 수행(→ D51 전역dedup·D52 한글 생성 적용). 원클릭 실행.
    False면 기존 수동 페이지 선택/캐시 재사용 흐름."""

    feature_gate: bool = False
    """Stage 1b(기능 통합) 후 Stage 2 진입 전, 기능 확정 게이트(D53)를 띄울지.
    True면 사용자가 도메인별 집계를 보고 불필요한 기능(leaf)을 제외 가능.
    False(기본)면 게이트 없이 전체 기능으로 바로 TC 설계(기존 동작)."""

    concurrency: int = 6
    """동시 LLM 호출 수(D55). Stage 2 그룹 설계·V10 보완 배치를 동시 실행.
    1이면 순차(기존 동작). 상용(Claude/OpenAI)은 RPM 제한 없어 병렬 효과 큼.
    Gemini 등 RPM 제한 모델은 내부적으로 간격 직렬화됨."""

    target_kind: str = "web"
    """시험 대상 유형 (D59): web | api_rest | api_code | gui. 기본 web(기존 동작).
    Stage 0(구조 스캔)·Stage 5(자동 실행)만 이 값으로 어댑터에 분기되고,
    Stage 1~4·6·7 코어는 불변."""

    target_config: dict = field(default_factory=dict)
    """대상 유형별 입력(D59). 예:
      api_rest  → {openapi_path|openapi_url, base_url, auth:{...}}
      api_code  → {lang, module_path|dll_path, signatures_path, sandbox:bool}
      gui       → {exe_path, args, window_title, log_paths, db}
    web는 기존 target_url/auth_sequence 등 상위 필드를 그대로 사용."""


class Orchestrator:
    """AWT Stage 0~7 실행 제어."""

    def __init__(
        self,
        config: RunConfig,
        progress_cb: Callable[[str], None] | None = None,
        raw_progress_cb: Callable[[str], None] | None = None,
        llm_client=None,
    ):
        """
        Args:
            progress_cb:     사용자 친화 메시지(humanize 후). humanize=None인 메시지는 받지 않음.
            raw_progress_cb: 원본(raw) 메시지 — humanize 전 단계. 상세 로그 패널용.
            llm_client:      주입할 LLM 클라이언트(테스트·풀런 데모용 Mock 등). None이면 LLMClient 생성.
        """
        self.config = config
        # _safe_cb 위에서 이미 설정됨
        self.run_dir = RUNS_DIR / config.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        # progress_cb를 CP949 안전 + 사용자 친화적 메시지 변환 래퍼로 감쌈
        from app.core.messages import humanize

        def _safe_cb(msg: str) -> None:
            # 1) 상세 로그: 원본 메시지 그대로 전달 (필터링 없음)
            if raw_progress_cb is not None:
                try:
                    raw_progress_cb(msg)
                except UnicodeEncodeError:
                    safe = msg.encode("ascii", errors="replace").decode("ascii")
                    try:
                        raw_progress_cb(safe)
                    except Exception:
                        pass
                except Exception:
                    pass

            # 2) 사용자 친화 로그: humanize 후 전달
            friendly = humanize(msg)
            if friendly is None:          # 내부 디버그 메시지 — 사용자 화면 표시 안 함
                return
            try:
                (progress_cb or (lambda m: None))(friendly)
            except UnicodeEncodeError:
                safe = friendly.encode("ascii", errors="replace").decode("ascii")
                (progress_cb or (lambda m: None))(safe)

        self._cb = _safe_cb
        self.llm = llm_client or LLMClient(
            api_key=config.api_key,
            run_id=config.run_id,
            model_override=config.model_override,
            model_overrides=config.model_overrides,
            progress_cb=self._cb,
        )
        self.tcs: list[dict] = []
        self.ingest_result: dict = {}
        self.new_defects: list[dict] = []   # Stage 6B 결과 (결함 카탈로그 신규 항목)
        self._stage = 0
        # 협력적 일시정지/중단 플래그 (UI가 set, stage5가 read)
        self._paused  = False
        self._stopped = False
        # 시험 추적성 정보 (박정훈 권고 — meta.json 보강용)
        self.stage2_failed_leaves: list[dict] = []      # [{idx, name, reason}, ...]
        self.stage2_excluded_leaves: list[dict] = []    # max_leaves cap으로 제외된 leaf

    # ── 일시정지/중단 ────────────────────────────────────────────────────
    def set_paused(self, paused: bool) -> None:
        self._paused = paused

    def is_paused(self) -> bool:
        return self._paused

    def set_stopped(self, stopped: bool) -> None:
        self._stopped = stopped

    def is_stopped(self) -> bool:
        return self._stopped

    # ── Stage 0 ──────────────────────────────────────────────────────────
    def run_stage0(self) -> dict | None:
        from app.adapters import get_adapter
        adapter = get_adapter(self.config.target_kind)
        label = adapter.label or self.config.target_kind
        self._cb(f"▶ Stage 0: 구조 스캔 [{label}]")
        self._stage = 0
        if adapter.probe is None:
            self._cb("  (이 대상은 Stage 0 스캔 없음 — 입력 파일/스펙만 사용)")
            return None
        return adapter.probe.scan(
            config=self.config,
            llm=self.llm,
            run_dir=self.run_dir,
            progress_cb=self._cb,
            should_stop=self.is_stopped,
        )

    def has_stage0_draft(self) -> bool:
        """이 run에 Stage 0 분석 결과(feature-spec-draft.json)가 이미 있는지."""
        draft = self.run_dir / "dom-scan" / "feature-spec-draft.json"
        return draft.exists()

    def load_stage0_draft(self) -> dict | None:
        """기존 Stage 0 분석 결과를 그대로 로드 (재스캔 없이 Stage 1로 진입).

        run_stage0()가 반환하던 draft dict와 동일한 형태를 반환한다.
        """
        import json
        draft_path = self.run_dir / "dom-scan" / "feature-spec-draft.json"
        if not draft_path.exists():
            return None
        try:
            draft = json.loads(draft_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        n_feat = len(draft.get("features", []))
        self._cb(f"♻ 기존 웹사이트 분석 결과 재사용 — 기능 {n_feat}개 (재스캔 생략)")
        self._stage = 0
        return draft

    # ── Stage 1 ──────────────────────────────────────────────────────────
    def run_stage1(self, feature_spec: dict | None = None) -> dict:
        self._cb("▶ Stage 1: 파일 파싱·정규화")
        self.ingest_result = stage1_ingest.ingest(
            files=self.config.input_files,
            run_dir=self.run_dir,
            feature_spec=feature_spec,
            progress_cb=self._cb,
        )
        # ── Stage 1b: LLM 의미 기준 기능 통합 (중복 병합) ──────────────────
        if self.config.consolidate_features and self.ingest_result.get("leaves"):
            consolidated, creport = stage1b_consolidate.consolidate(
                self.ingest_result["leaves"],
                llm_client=self.llm,
                progress_cb=self._cb,
                should_stop=self.is_stopped,
            )
            self.ingest_result["leaves"] = consolidated
            self.ingest_result["consolidate_report"] = creport
        # ── D52: 최종 대분류 통제 어휘 sweep ──────────────────────────────────
        # consolidate(LLM)가 통제 어휘 밖 대분류를 생성했을 수 있으므로 한 번 더 보정.
        # _refine_leaves에서 이미 보정된 값은 idempotent(그대로 유지).
        leaves = self.ingest_result.get("leaves") or []
        if leaves:
            from app.core.taxonomy import classify_major
            swept = 0
            for lf in leaves:
                # 도메인 우선 분류 — leaf·중분류 컨텍스트 전달(2축 분리, 아이디어 A)
                canon, status = classify_major(
                    lf.get("category_major", "") or "",
                    lf.get("category_mid", ""),
                    lf.get("category_leaf", ""),
                )
                if canon != (lf.get("category_major", "") or ""):
                    lf.setdefault("category_major_raw", lf.get("category_major", ""))
                    lf["category_major"] = canon
                    swept += 1
            if swept:
                self._cb(f"  대분류 통제 어휘 보정(통합 후) — {swept}개 추가 정규화")
        self._stage = 1
        return self.ingest_result

    # ── Stage 2 ──────────────────────────────────────────────────────────
    def run_stage2(self) -> list[dict]:
        self._cb("▶ Stage 2: TC 설계")
        # 추적성 정보를 받아둘 리스트 — 시험인증 보고서/메타에 기록
        self.stage2_failed_leaves   = []
        self.stage2_excluded_leaves = []
        self.tcs = stage2_tc_design.design(
            leaves=self.ingest_result["leaves"],
            manual_text=self.ingest_result["manual_text"],
            llm_client=self.llm,
            max_leaves=self.config.max_leaves,
            progress_cb=self._cb,
            failed_leaves_out=self.stage2_failed_leaves,
            excluded_leaves_out=self.stage2_excluded_leaves,
            should_stop=self.is_stopped,
            concurrency=self.config.concurrency,
            design_contract=("TC_DESIGN_API"
                             if self.config.target_kind in ("api_rest", "api_code")
                             else "TC_DESIGN_GROUP"),
        )
        self._save_intermediate("tc_raw")
        self._stage = 2
        return self.tcs

    # ── Stage 2 이후 TC 수 검사 ──────────────────────────────────────────
    def _assert_tcs_not_empty(self, stage_name: str) -> None:
        """TC 목록이 비어있으면 명확한 메시지로 중단."""
        if not self.tcs:
            raise RuntimeError(
                f"{stage_name}: TC가 0개입니다.\n"
                "가능한 원인:\n"
                "  1) 대상 URL에 접근 실패 (Stage 0 DOM 스캔 결과 없음)\n"
                "  2) 매뉴얼 파일 없음 + DOM 기능도 0개 추출\n"
                "  3) LLM API 오류로 모든 leaf 분석 실패 (Gemini 안전 필터/일일 쿼터 등)\n"
                "  4) Stage 2 첫 호출이 빈 응답으로 차단됨 (RECITATION/SAFETY)\n"
                "로그에서 '기능 분석 실패' / '안전 필터' 메시지를 확인하세요."
            )

    # ── Stage 3 ──────────────────────────────────────────────────────────
    def run_stage3(self) -> list[dict]:
        self._cb("▶ Stage 3: V1~V5 검증")
        self._assert_tcs_not_empty("Stage 3")
        self.tcs = stage3_verify.verify(
            tcs=self.tcs,
            manual_text=self.ingest_result["manual_text"],
            llm_client=self.llm,
            leaves=self.ingest_result["leaves"],
            inferred_threshold=self.config.inferred_threshold,
            progress_cb=self._cb,
            concurrency=self.config.concurrency,
        )
        self._save_intermediate("tc_verified")
        # Reviewer Gate용 Excel 생성 (TC 있을 때만)
        if self.tcs:
            build_review(self.tcs, self.run_dir / "tc_review.xlsx")
        self._stage = 3
        return self.tcs

    # ── Stage 4 (UI) ─────────────────────────────────────────────────────
    def apply_gate_decisions(self, decisions: dict[str, dict]) -> list[dict]:
        """UI에서 받은 A/E/R/P 결정을 TC에 반영."""
        self._cb("▶ Stage 4: Reviewer Gate 반영")
        for tc in self.tcs:
            d = decisions.get(tc["tc_id"])
            if d:
                tc["review_status"] = d.get("status", tc["review_status"])
                tc["reviewer_note"] = d.get("note", "")
                tc["reviewer_id"] = d.get("reviewer_id", "")
        self._save_intermediate("tc_gated")
        self._stage = 4
        return self.tcs

    # ── Stage 5 ──────────────────────────────────────────────────────────
    def run_stage5(self) -> list[dict]:
        from app.adapters import get_adapter
        from app.adapters.grading import annotate_grades
        adapter = get_adapter(self.config.target_kind)
        self._cb(f"▶ Stage 5: 자동 실행 [{adapter.label or self.config.target_kind}]")
        # 시작 전 플래그 리셋 (이전 실행이 중단된 상태일 수 있음)
        self._paused  = False
        self._stopped = False
        # 비웹 대상: 실행 전 LLM으로 test_data 보강(명세-의존 값). 실패 시 휴리스틱 폴백.
        if self.config.target_kind in ("api_rest", "api_code"):
            self._enrich_test_data()
        self.tcs = adapter.executor.execute(
            tcs=self.tcs,
            config=self.config,
            run_dir=self.run_dir,
            progress_cb=self._cb,
            is_paused=self.is_paused,
            is_stopped=self.is_stopped,
        )
        # 자동화 등급/대상 메타 주석 (target_kind/target_stability/automation_grade)
        annotate_grades(self.tcs, adapter)
        self._save_intermediate("tc_executed")
        self._stage = 5
        return self.tcs

    def _enrich_test_data(self) -> None:
        """실행 직전 — 비웹 TC에 LLM이 명세-의존 test_data를 주입(D67, 작업1-B).

        leaf별로 TC를 묶어, 해당 leaf 명세(매뉴얼 발췌)를 근거로 LLM에 요청.
        LLM 미가용/오류 시 조용히 폴백(실행기는 휴리스틱 value_synth 사용).
        """
        try:
            from app.adapters import llm_test_data
            from app.core.stage1_ingest import excerpt_for_leaf
        except Exception:
            return
        leaves = self.ingest_result.get("leaves") or []
        leaf_by_name = {lf.get("category_leaf"): lf for lf in leaves}
        manual = self.ingest_result.get("manual_text", "")
        runnable = [tc for tc in self.tcs
                    if tc.get("review_status") in ("approved", "edited")
                    and not tc.get("test_data")]
        if not runnable:
            return
        groups: dict[str, list[dict]] = {}
        for tc in runnable:
            groups.setdefault(tc.get("소분류", ""), []).append(tc)
        self._cb(f"  test_data 보강 — {len(groups)}개 기능, {len(runnable)}개 TC")
        for leafname, tcs in groups.items():
            lf = leaf_by_name.get(leafname)
            spec = excerpt_for_leaf(manual, lf) if lf else leafname
            try:
                llm_test_data.enrich(self.llm, self.config.target_kind, spec or leafname, tcs)
            except Exception:
                pass  # 폴백: 실행기 휴리스틱

    # ── Stage 6 ──────────────────────────────────────────────────────────
    def run_stage6(self) -> list[dict]:
        self._cb("▶ Stage 6: 실패 원인 분석")
        self.tcs = stage6_enhance.enhance(
            tcs=self.tcs,
            llm_client=self.llm,
            progress_cb=self._cb,
        )
        self._stage = 6
        return self.tcs

    # ── Stage 6B ─────────────────────────────────────────────────────────
    def run_stage6b(
        self,
        product_type_id: str = "BOARD_CMS",
        actor_username: str = "awt_system",
        db=None,
    ) -> list[dict]:
        """Stage 6 완료 후 real_defect TC를 결함 카탈로그에 자동 피드백."""
        self._cb("▶ Stage 6B: 결함 카탈로그 피드백")
        self.new_defects = stage6b_defect_feedback.feedback(
            tcs=self.tcs,
            llm_client=self.llm,
            product_type_id=product_type_id,
            run_id=self.config.run_id,
            actor_username=actor_username,
            db=db,
            progress_cb=self._cb,
        )
        return self.new_defects

    # ── Stage 7 ──────────────────────────────────────────────────────────
    def run_stage7(self) -> Path:
        self._cb("▶ Stage 7: Excel 최종 산출")
        out = stage7_output.output(
            tcs=self.tcs,
            run_dir=self.run_dir,
            progress_cb=self._cb,
        )
        self._stage = 7
        return out

    # ── 편의 메서드 ─────────────────────────────────────────────────────
    def run_pipeline(
        self,
        skip_stage0: bool = False,
        gate_decisions: dict | None = None,
    ) -> Path:
        """Stage 0~7 전체 실행 (Stage 4 결정은 gate_decisions로 주입)."""
        feature_spec = None
        if not skip_stage0:
            feature_spec = self.run_stage0()

        self.run_stage1(feature_spec)
        self.run_stage2()
        self.run_stage3()
        self.apply_gate_decisions(gate_decisions or {})
        self.run_stage5()
        self.run_stage6()
        return self.run_stage7()

    def load_from_stage3(self, run_id: str | None = None) -> bool:
        """기존 tc_verified.json 로드 — Stage 4부터 재개할 때 사용.

        Args:
            run_id: 불러올 run ID. None이면 self.config.run_id 사용.
        Returns:
            True if loaded successfully, False otherwise.
        """
        import json
        target_run = run_id or self.config.run_id
        path = RUNS_DIR / target_run / "tc_verified.json"
        if not path.exists():
            return False
        self.tcs = json.loads(path.read_text(encoding="utf-8"))
        # ingest_result 복원: manual.txt 에서 재파싱
        manual_path = RUNS_DIR / target_run / "ingest" / "manual.txt"
        if manual_path.exists():
            manual_text = manual_path.read_text(encoding="utf-8")
            from app.core import stage1_ingest
            leaves = stage1_ingest._extract_leaves_from_text(manual_text)
            self.ingest_result = {"manual_text": manual_text, "leaves": leaves}
        self.run_dir = RUNS_DIR / target_run
        self._stage = 3
        return True

    def load_from_stage4(self, run_id: str | None = None) -> bool:
        """기존 tc_gated.json 로드 — Stage 5부터 재개할 때 사용 (Gate 결정 보존).

        Returns:
            True if loaded successfully, False otherwise.
        """
        import json
        target_run = run_id or self.config.run_id
        path = RUNS_DIR / target_run / "tc_gated.json"
        if not path.exists():
            return False
        self.tcs = json.loads(path.read_text(encoding="utf-8"))
        manual_path = RUNS_DIR / target_run / "ingest" / "manual.txt"
        if manual_path.exists():
            manual_text = manual_path.read_text(encoding="utf-8")
            from app.core import stage1_ingest
            leaves = stage1_ingest._extract_leaves_from_text(manual_text)
            self.ingest_result = {"manual_text": manual_text, "leaves": leaves}
        self.run_dir = RUNS_DIR / target_run
        self._stage = 4
        return True

    @staticmethod
    def suggest_resume_stage(run_dir: Path) -> int | None:
        """run 디렉토리의 산출물을 보고 어느 stage부터 재개 가능한지 추정.

        Returns:
            5 = Stage 5~7 재개 (tc_gated.json 있음, Gate 결정 보존)
            4 = Stage 4 (Reviewer Gate) 재개 (tc_verified.json 있음)
            None = 재개 불가 (Stage 1~3을 처음부터 해야 함)
        """
        if (run_dir / "tc_gated.json").exists():
            return 5
        if (run_dir / "tc_verified.json").exists():
            return 4
        return None

    def _save_intermediate(self, name: str) -> None:
        import json
        path = self.run_dir / f"{name}.json"
        path.write_text(
            json.dumps(self.tcs, ensure_ascii=False, indent=2), encoding="utf-8"
        )
