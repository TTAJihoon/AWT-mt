"""AWT 진입점 — PySide6 앱 초기화 및 창 연결 (D45, D46)."""
from __future__ import annotations
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from app.auth.db_client import DBClient
from app.config.db_config import DBConfig
from app.config.settings import load_api_key, get_active_provider
from app.ui.login_window import LoginWindow
from app.ui.dashboard import Dashboard
from app.ui.wizard import RunWizard
from app.ui.pipeline_view import PipelineView
from app.ui.reviewer_gate import ReviewerGate
from app.ui.theme import APPLE_QSS
from app.core.orchestrator import RunConfig


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("AWT")
    app.setApplicationVersion("1.0.0")
    app.setStyle("Fusion")
    app.setStyleSheet(APPLE_QSS)

    # 첫 실행: 중앙 DB 접속 설정 입력(현재값 pre-fill). 취소해도 특별 관리자 계정으로 진입 가능.
    from app.config.settings import has_db_settings
    from app.ui.db_settings_dialog import DbSettingsDialog
    if not has_db_settings():
        DbSettingsDialog().exec()

    # DB 설정 (저장값 > 환경변수 > 기본값)
    db_cfg = DBConfig.from_env()
    db = DBClient(db_cfg)

    # ── 로그인 ────────────────────────────────────────────────────────────
    login = LoginWindow(db_config=db_cfg)

    token: str = ""
    username: str = ""
    api_key: str = ""
    role: str = "reviewer"

    def _on_logged_in(t: str, u: str, k: str) -> None:
        nonlocal token, username, api_key, role
        token, username, api_key = t, u, k
        from app.auth.special_account import is_special_token
        if is_special_token(t):
            role = "admin"          # 특별 관리자 계정 — DB 세션 조회 없이 admin
            return
        try:
            session_info = db.validate_session(t)
            role = session_info["role"] if session_info else "reviewer"
        except Exception:
            role = "reviewer"       # DB 오류 시 안전 기본값

    login.logged_in.connect(_on_logged_in)
    if login.exec() != LoginWindow.Accepted:
        sys.exit(0)

    # ── 대시보드 ──────────────────────────────────────────────────────────
    _pipeline_views: list[PipelineView] = []
    dash: Dashboard | None = None

    def _make_dashboard() -> None:
        nonlocal dash
        dash = Dashboard(token=token, username=username, role=role, api_key=api_key, db=db)
        dash.new_run_requested.connect(_open_wizard)
        dash.open_run_requested.connect(_reopen_run)
        dash.clone_run_requested.connect(_clone_run)
        dash.resume_run_requested.connect(_resume_run)
        dash.logout_requested.connect(_do_logout)
        dash.show()

    def _resume_run(run_id: str, from_stage: int) -> None:
        """이력에서 우클릭 → 'Stage N부터 재개'.

        from_stage:
          4 = Reviewer Gate부터 (tc_verified.json 로드)
          5 = Stage 5~7부터 (tc_gated.json 로드)
        """
        import json
        from pathlib import Path as _P

        run_dir = _P("data/runs") / run_id
        meta_path = run_dir / "meta.json"
        if not meta_path.exists():
            QMessageBox.warning(dash, "재개 불가", f"meta.json이 없습니다: {run_id}")
            return
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as e:
            QMessageBox.critical(dash, "재개 오류", f"meta.json 로드 실패: {e}")
            return

        cfg = _config_from_meta(run_id, meta)
        pv = _spawn_pipeline(cfg)

        # 재개 — orchestrator에 데이터 로드 + 적절한 stage 활성화
        try:
            if from_stage == 4:
                if not pv._orch.load_from_stage3(run_id=run_id):
                    QMessageBox.warning(pv, "재개 실패", "tc_verified.json 로드 실패")
                    return
                pv._tcs = pv._orch.tcs
                pv._max_progress = 3
                pv._update_circles(4, "Stage 4 — Reviewer Gate 대기")
                pv._set_status(f"Stage 3 완료 (재개)  |  TC {len(pv._tcs)}개", active=True, running=False)
                pv._run_btn.setVisible(False)
                pv._gate_btn.setVisible(True)
                pv._gate_btn.setEnabled(True)
                pv._exec_btn.setVisible(True)
                pv._exec_btn.setEnabled(False)
                pv._headless_cb.setVisible(True)
                pv._refresh_tc_table()
                # Stage 0 산출물 있으면 다운로드 버튼 노출
                if (pv._orch.run_dir / "dom-scan" / "feature-spec-draft.json").exists():
                    pv._feature_dl_btn.setVisible(True)
                    pv._feature_csv_btn.setVisible(True)
                if (pv._orch.run_dir / "dom-scan" / "screenshots").exists():
                    pv._screenshot_dir_btn.setVisible(True)
                pv._append_log(f"🔄 Stage 4부터 재개 — TC {len(pv._tcs)}개 로드됨")
            elif from_stage == 5:
                if not pv._orch.load_from_stage4(run_id=run_id):
                    QMessageBox.warning(pv, "재개 실패", "tc_gated.json 로드 실패")
                    return
                pv._tcs = pv._orch.tcs
                pv._max_progress = 4
                pv._update_circles(5, "Stage 5 대기 (재개)")
                pv._set_status(f"Stage 4 완료 (재개)  |  TC {len(pv._tcs)}개", active=True, running=False)
                pv._run_btn.setVisible(False)
                pv._gate_btn.setVisible(False)
                pv._exec_btn.setVisible(True)
                pv._exec_btn.setEnabled(True)
                pv._exec_btn.setText("Stage 5~7 실행")
                pv._headless_cb.setVisible(True)
                pv._refresh_tc_table()
                if (pv._orch.run_dir / "dom-scan" / "feature-spec-draft.json").exists():
                    pv._feature_dl_btn.setVisible(True)
                    pv._feature_csv_btn.setVisible(True)
                if (pv._orch.run_dir / "dom-scan" / "screenshots").exists():
                    pv._screenshot_dir_btn.setVisible(True)
                pv._append_log(f"🔄 Stage 5부터 재개 — TC {len(pv._tcs)}개 로드됨 (Gate 결정 보존)")
            else:
                QMessageBox.warning(pv, "재개 실패", f"지원하지 않는 stage: {from_stage}")
        except Exception as e:
            import traceback
            QMessageBox.critical(pv, "재개 오류", traceback.format_exc()[:1200])

    def _open_wizard() -> None:
        # 설정 탭에서 키를 저장한 경우를 위해 항상 최신값 로드
        current_key = load_api_key() or api_key
        if not current_key or current_key.startswith("AIza여기에") or current_key.startswith("sk-ant-여기에") or current_key.startswith("sk-여기에"):
            # 키 미설정 → 바로 입력 다이얼로그 (설정 탭까지 가지 않아도 됨)
            from PySide6.QtWidgets import QDialog
            from app.ui.api_key_dialog import ApiKeyDialog
            if ApiKeyDialog(parent=dash).exec() != QDialog.Accepted:
                return
            current_key = load_api_key() or ""
            if not current_key:
                return
        wiz = RunWizard(api_key=current_key, parent=dash)
        wiz.run_config_ready.connect(_start_pipeline)
        wiz.exec()

    def _spawn_pipeline(config) -> "PipelineView":
        """PipelineView 생성 + Reviewer Gate/재생성 핸들러 와이어링 + 표시.

        _start_pipeline / _resume_run / _reopen_run(처음부터 실행) 공용.
        반환된 pv에 대해 호출자가 추가로 stage 상태를 세팅할 수 있다.
        """
        pv = PipelineView(config=config, parent=None)
        _pipeline_views.append(pv)

        def _on_tcs_regenerated(new_tcs: list[dict]) -> None:
            pv._tcs = new_tcs
            pv._orch.tcs = new_tcs
            pv._orch._save_intermediate("tc_verified")  # 중간 저장 (이후 재개 가능)
            pv._refresh_tc_table()
            pv._append_log(f"🔄 거부 TC 재생성 — 총 {len(new_tcs)}개 (검토 후 다시 확정)")

        def _open_gate(tcs: list[dict]) -> None:
            try:
                manual_text = ""
                try:
                    manual_text = pv._orch.ingest_result.get("manual_text", "")
                except Exception:
                    pass
                gate = ReviewerGate(
                    tcs=tcs, reviewer_id=username, parent=pv,
                    llm_client=pv._orch.llm,
                    manual_text=manual_text,
                    run_dir=getattr(pv._orch, "run_dir", None),   # D58 — 스크린샷 조회
                )
                gate.decisions_ready.connect(pv.apply_gate)
                gate.tcs_regenerated.connect(_on_tcs_regenerated)
                gate.raise_()
                gate.activateWindow()
                gate.exec()
            except Exception:
                import traceback
                QMessageBox.critical(pv, "Stage 4 오류", traceback.format_exc()[:1200])

        pv.gate_review_requested.connect(_open_gate)
        pv.clone_requested.connect(_clone_run)   # 실행 정보 → 설정 복제·재실행
        pv.show()
        return pv

    def _start_pipeline(config) -> None:
        _spawn_pipeline(config)

    def _config_from_meta(run_id: str, meta: dict) -> "RunConfig":
        """meta.json → RunConfig 복원 (재개·재실행 공용)."""
        current_key = load_api_key() or api_key
        return RunConfig(
            api_key=current_key,
            target_url=meta.get("target_url", ""),
            input_files=meta.get("input_files") or [],
            auth_sequence=meta.get("auth_sequence") or [],
            run_id=run_id,
            inferred_threshold=meta.get("inferred_threshold", 0.30),
            max_leaves=meta.get("max_leaves", 50),
            model_override=meta.get("model_override"),
            model_overrides=meta.get("model_overrides") or None,
            max_pages=meta.get("max_pages", 30),
            headless_exec=meta.get("headless_exec", True),
            slow_mo_ms=meta.get("slow_mo_ms", 0),
            target_kind=meta.get("target_kind", "web"),        # D59 — 비웹 대상 복원
            target_config=meta.get("target_config") or {},
        )

    def _reopen_run(run_id: str) -> None:
        """이력 더블클릭 — 진행 중이면 포커스, 완료면 Excel, 그 외엔 적절한 단계부터 이어서 진행."""
        import json
        # ① 열려 있는 PipelineView 탐색 (최소화 상태도 포함)
        for pv in _pipeline_views:
            if (hasattr(pv, "config")
                    and pv.config.run_id == run_id
                    and not pv.isHidden()):
                if pv.isMinimized():
                    pv.showNormal()
                pv.raise_()
                pv.activateWindow()
                return

        run_dir = Path("data/runs") / run_id
        meta_path = run_dir / "meta.json"
        meta: dict = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
        stage = (meta.get("stage") or "").lower()

        # ② 완료된 실행 — tc_final.xlsx 열기
        tc_final = run_dir / "tc_final.xlsx"
        if stage == "done" and tc_final.exists():
            import subprocess
            subprocess.Popen(["explorer", str(tc_final)])
            return

        # ③ 중간 완료 단계가 있으면 그 지점부터 재개
        #    tc_gated.json → Stage 5~7,  tc_verified.json → Stage 4 (Reviewer Gate)
        from app.core.orchestrator import Orchestrator
        resume_stage = Orchestrator.suggest_resume_stage(run_dir)
        if resume_stage is not None:
            _resume_run(run_id, resume_stage)
            return

        # ④ 산출물이 없으면(설정만 됨) → 저장된 설정으로 Stage 1~3 실행 화면 오픈
        if not meta:
            QMessageBox.information(
                dash, "실행 정보",
                f"Run ID: {run_id}\n"
                "meta.json이 없어 이어서 진행할 수 없습니다.\n"
                "새 실행을 시작하거나 우클릭 → 복제로 재실행하세요.",
            )
            return
        cfg = _config_from_meta(run_id, meta)
        pv = _spawn_pipeline(cfg)
        pv._append_log(
            f"📂 이력에서 다시 열기 — 저장된 설정 복원 완료. "
            f"'Stage 1~3 실행'을 눌러 이어서 진행하세요."
        )

    def _clone_run(run_id: str) -> None:
        """이력 우클릭 → 복제: 그 실행의 모든 스텝 설정을 복사해 새 마법사 prefill."""
        import json
        current_key = load_api_key() or api_key
        if not current_key or current_key.startswith("AIza여기에") or current_key.startswith("sk-ant-여기에") or current_key.startswith("sk-여기에"):
            QMessageBox.warning(
                dash, "API Key 미설정",
                "LLM API Key가 설정되지 않았습니다.\n"
                "대시보드 → 설정 탭에서 API Key를 먼저 저장해주세요."
            )
            return
        # meta.json에서 전체 설정 복원 → wizard prefill_config로 전달
        meta: dict = {}
        meta_path = Path("data/runs") / run_id / "meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                meta = {}

        # 구버전 run 감지: auth_sequence 키 자체가 없으면 인증 정보가 저장되기 전
        # (D73 이전) 생성된 run → Step 2를 복원할 수 없으므로 사용자에게 안내.
        # 키가 있는데 빈 리스트면 '애초에 로그인 불필요'이므로 안내하지 않음.
        if meta and "auth_sequence" not in meta:
            QMessageBox.information(
                dash, "복제 안내",
                "이 실행은 인증 시퀀스(Step 2) 저장 기능이 추가되기 전에 생성되어\n"
                "로그인 단계 정보가 남아 있지 않습니다.\n\n"
                "URL·파일·옵션은 복원되지만, 로그인이 필요한 사이트라면\n"
                "Step 2에서 인증 단계를 다시 입력해 주세요.\n"
                "(이후 새로 실행하는 건은 인증 시퀀스까지 모두 복제됩니다.)"
            )

        wiz = RunWizard(
            api_key=current_key,
            prefill_url=meta.get("target_url", ""),
            prefill_config=meta or None,
            parent=dash,
        )
        wiz.run_config_ready.connect(_start_pipeline)
        wiz.exec()

    def _do_logout() -> None:
        """로그아웃 → 대시보드 닫고 로그인 화면 재표시."""
        nonlocal token, username, api_key, role, dash
        if dash:
            dash.close()
            dash = None
        new_login = LoginWindow(db_config=db_cfg)
        new_login.logged_in.connect(_on_logged_in)
        if new_login.exec() == LoginWindow.Accepted:
            _make_dashboard()
        else:
            app.quit()

    _make_dashboard()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
