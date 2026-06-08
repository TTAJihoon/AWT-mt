"""LLM 호출 래퍼 — provider 추상화 (D48) + stateless 호출 (D38) + 캐시 (D41).

각 Contract의 frontmatter `model:` 필드 prefix에 따라 provider가 자동 선택된다:
    claude-*  → AnthropicProvider
    gpt-*, o1-*, o3-* → OpenAIProvider
    gemini-*  → GeminiProvider

상세: doc/07-llm-providers.md
"""
from __future__ import annotations
import json
import re
import threading
import time
from pathlib import Path
from typing import Any

from app.api.call_contracts import Contract, load as load_contract
from app.api.providers import provider_name_for_model, resolve_provider, LLMProvider
from app.tools import cache as cache_store

_LOG_DIR = Path("data/runs")


def _extract_retry_delay(err_str: str) -> int | None:
    """API 오류 응답의 'retryDelay' 필드에서 권장 대기 시간(초)을 추출."""
    m = re.search(r"'retryDelay':\s*'(\d+)s'", err_str)
    if m:
        return int(m.group(1))
    # "Please retry in N.Ns" 형식도 처리
    m2 = re.search(r"retry in (\d+)[\.\d]*s", err_str)
    if m2:
        return int(m2.group(1))
    return None


class LLMClient:
    """LLM 호출 진입점. Stage 코드는 이 클래스의 .call()만 사용한다."""

    # 모델별 최소 호출 간격(초) — free tier RPM 기반
    _MIN_INTERVAL: dict[str, float] = {
        "gemini-3.5-flash":      13.0,  # 5 RPM → 60/5 = 12s + 1s 여유
        "gemini-3.1-flash-lite":  6.0,  # 10 RPM → 60/10 = 6s
        "gemini-2.5-flash":      13.0,
        "gemini-2.5-flash-lite":  6.0,
        "gemini-2.0-flash":       6.0,
        "gemini-2.0-flash-lite":  6.0,
        "gemini-1.5-flash":       5.0,
        "gemma-4-26b-a4b-it":   12.0,   # Gemma 4 26B (preview — 500 오류 방지용 보수적 간격)
        "gemma-4-31b-it":       12.0,   # Gemma 4 31B
    }

    def __init__(
        self,
        api_key: str,
        run_id: str,
        provider_override: str | None = None,
        model_override: str | None = None,
        model_overrides: dict[str, str] | None = None,
        progress_cb: Any = None,
    ):
        """
        Args:
            api_key: 선택된 provider의 API 키 (UI/.env에서 주입)
            run_id: 실행 ID — 로그 디렉터리 구분
            provider_override: 명시적 provider 이름 (테스트·실험용). 통상은 None — Contract model에서 자동 라우팅
            model_override: Contract frontmatter의 model을 이 값으로 교체 (전역 기본).
                예) "gemini-3.5-flash" 설정 시 모든 Contract가 Gemini로 실행됨.
                None이면 각 Contract의 model을 그대로 사용.
            model_overrides: 단계(contract_id)별 모델 지정 맵. 예) {"DOM_SPEC":"gpt-5.4-nano"}.
                우선순위: model_overrides[contract_id] > model_override > contract.model
            progress_cb: 재시도 메시지를 GUI 로그로 전달하기 위한 콜백 (선택)
        """
        self._api_key = api_key
        self._run_id = run_id
        self._provider_override = provider_override
        self._model_override = model_override
        self._model_overrides = model_overrides or {}
        self._progress_cb = progress_cb
        self._log_dir = _LOG_DIR / run_id / "llm"
        self._log_dir.mkdir(parents=True, exist_ok=True)
        # provider 인스턴스 캐시 — 같은 provider는 1회만 생성
        self._providers: dict[str, LLMProvider] = {}
        # RPM 제어 — 마지막 실제 API 호출 시각
        self._last_call_time: float = 0.0
        # 동시성(D55) — 공유 상태(provider 캐시·RPM·캐시·로그) 보호
        self._lock = threading.Lock()
        self._log_seq = 0

    def _get_provider(self, model: str) -> LLMProvider:
        name = self._provider_override or provider_name_for_model(model)
        with self._lock:
            if name not in self._providers:
                key = self._key_for_provider(name)
                self._providers[name] = resolve_provider(model, key)
            return self._providers[name]

    def _key_for_provider(self, provider_name: str) -> str:
        """모델이 가리키는 provider에 '맞는' API 키를 반환.

        생성자에서 받은 self._api_key는 한 provider용일 뿐이라,
        model_override가 다른 provider 모델일 때(재개·복제 등) 키가 어긋난다.
        → provider별 키를 settings에서 직접 조회해 불일치를 방지.
        (예: 구글 키가 OpenAI 엔드포인트로 가서 401 나는 문제)
        """
        try:
            from app.config.settings import load_api_key, get_active_provider
            # 생성자 키가 이 provider용이면(활성 provider와 일치) 그대로 사용
            if provider_name == get_active_provider() and self._api_key:
                return self._api_key
            key = load_api_key(provider_name)
            if key:
                return key
        except Exception:
            pass
        return self._api_key

    def call(
        self,
        contract_id: str,
        inputs: dict[str, Any],
        use_cache: bool = True,
        _retry_count: int = 0,
    ) -> dict:
        """Contract 1회 호출. 캐시 히트 시 API 미호출.

        503/429 일시 오류는 최대 3회 지수 백오프 재시도.
        """
        contract = load_contract(contract_id)
        # 모델 우선순위: 단계별 지정 > 전역 override > Contract 기본
        effective_model = (
            self._model_overrides.get(contract_id)
            or self._model_override
            or contract.model
        )

        # Active provider 자동 교체:
        # 명시적 override가 없는 경우, 사용자가 설정 탭에서 선택한 provider와
        # contract 모델의 provider가 다르면 active provider의 기본 모델로 교체.
        # 예) active=openai, contract model=claude-sonnet-4-6 → gpt-4o로 교체
        if not self._model_overrides.get(contract_id) and not self._model_override:
            try:
                from app.config.settings import (
                    get_active_provider, get_provider_model,
                )
                active_prov = get_active_provider()
                natural_prov = provider_name_for_model(effective_model)
                if active_prov != natural_prov:
                    effective_model = get_provider_model(active_prov) or effective_model
            except Exception:
                pass

        # 캐시 키에 model 포함 (다른 모델은 다른 결과 — D48)
        cache_inputs = dict(inputs)
        cache_inputs["__model__"] = effective_model
        if use_cache:
            with self._lock:
                cached = cache_store.get(contract_id, contract.version, cache_inputs)
            if cached is not None:
                return cached

        user_msg = contract.render_user(**inputs)
        provider = self._get_provider(effective_model)

        # 호출 직전 provider/model 진단 로그
        try:
            prov_name = provider_name_for_model(effective_model)
            if self._progress_cb:
                self._progress_cb(f"[LLM] {contract_id} → {prov_name} / {effective_model}")
        except Exception:
            pass

        # RPM 스로틀링 — 모델별 최소 간격 적용 (캐시 히트는 제외됨)
        # 동시성(D55): min_interval>0(Gemini 등)은 락으로 간격을 직렬화해 RPM 보존.
        # min_interval=0(상용 Claude/OpenAI)은 블록 건너뜀 → 완전 병렬.
        min_interval = self._MIN_INTERVAL.get(effective_model, 0.0)
        if min_interval > 0 and _retry_count == 0:
            with self._lock:
                elapsed_since_last = time.time() - self._last_call_time
                if elapsed_since_last < min_interval:
                    time.sleep(min_interval - elapsed_since_last)
                self._last_call_time = time.time()

        start = time.time()

        try:
            result_chat = provider.chat(
                system=contract.system_prompt,
                user=user_msg,
                model=effective_model,
                max_tokens=contract.max_output_tokens,
                json_mode=True,
            )
        except Exception as e:
            # ── 오류 분류 ───────────────────────────────────────────────────────
            err_str = str(e)

            prov_name = provider_name_for_model(effective_model)

            # 모델 없음(404) — 모델명 오타/미존재
            if any(code in err_str for code in (
                "model_not_found", "does not exist", "No such model",
                "model not found", "invalid_model",
            )):
                raise RuntimeError(
                    f"모델을 찾을 수 없습니다: {effective_model}\n\n"
                    f"대시보드 → 설정 탭에서 [{prov_name}] 기본 모델을 올바르게 입력해 주세요.\n"
                    f"  Anthropic 예시 : claude-sonnet-4-6\n"
                    f"  OpenAI 예시    : gpt-4o, gpt-4o-mini\n"
                    f"  Google 예시    : gemini-2.5-flash"
                ) from e

            # 인증 오류(401) — API 키 잘못됨, 재시도 무의미
            if any(code in err_str for code in (
                "401", "Incorrect API key", "Invalid API key",
                "AuthenticationError", "PermissionDeniedError",
                "API_KEY_INVALID", "invalid_api_key",
            )):
                raise RuntimeError(
                    f"API 키가 올바르지 않습니다.\n"
                    f"  사용 Provider : {prov_name}\n"
                    f"  사용 모델     : {effective_model}\n\n"
                    f"대시보드 → 설정 탭에서 [{prov_name}] API 키를 확인해 주세요."
                ) from e

            # 일일 쿼터 초과(PerDay) — 재시도해도 해결 안 됨, 즉시 중단
            if "429" in err_str and "PerDay" in err_str:
                raise RuntimeError(
                    "Gemini API 일일 쿼터 초과 — 무료 플랜은 모델당 20회/일입니다.\n"
                    "오늘 사용 가능한 호출 횟수를 모두 소진했습니다.\n"
                    "\n"
                    "해결 방법:\n"
                    "  1) 내일 다시 실행 (무료 플랜 유지)\n"
                    "  2) Google AI Studio에서 유료 플랜으로 업그레이드\n"
                    "  3) max_leaves 값을 더 낮게 설정해 호출 횟수 줄이기"
                ) from e

            # 일시적 서버/속도 오류 — 최대 5회 재시도 (503·500·분당 429·빈 응답)
            # 500 INTERNAL: Gemini 서버 과부하 (일시적)
            # 503 UNAVAILABLE / 429 RESOURCE_EXHAUSTED: 분당 속도 제한
            # [TRANSIENT]: gemini_provider가 명시한 일시 장애 (빈 응답 등)
            if _retry_count < 5 and any(
                code in err_str for code in (
                    "500", "503", "429",
                    "INTERNAL", "UNAVAILABLE", "RESOURCE_EXHAUSTED",
                    "[TRANSIENT]",
                )
            ):
                # API가 권장 대기 시간을 제공하면 그 값 사용; 없으면 지수 백오프
                suggested = _extract_retry_delay(err_str)
                wait_sec = (suggested + 3) if suggested else (15 * (2 ** _retry_count))
                wait_sec = min(wait_sec, 300)  # 최대 5분
                try:
                    self._log_retry(contract_id, _retry_count + 1, wait_sec, err_str)
                except Exception:
                    pass  # 로그 실패가 재시도를 막지 않도록
                time.sleep(wait_sec)
                return self.call(contract_id, inputs, use_cache, _retry_count + 1)
            raise

        elapsed = time.time() - start
        result = self._parse_json(result_chat.text)

        self._log(
            contract_id=contract_id,
            provider_name=provider.name,
            inputs=inputs,
            user_msg=user_msg,
            raw=result_chat.text,
            parsed=result,
            elapsed=elapsed,
            input_tokens=result_chat.input_tokens,
            output_tokens=result_chat.output_tokens,
            model=result_chat.model,
        )

        if use_cache:
            with self._lock:
                cache_store.put(contract_id, contract.version, cache_inputs, result)

        return result

    def _log_retry(self, contract_id: str, attempt: int, wait_sec: int, err: str) -> None:
        import sys
        # 오류 메시지에서 핵심 상태 코드만 추출 (긴 traceback 제거)
        err_summary = err.splitlines()[0][:100] if err else ""
        msg = (
            f"  [재시도 {attempt}/5] {contract_id} - {wait_sec}초 대기 중... "
            f"({err_summary})"
        )
        # GUI progress_cb 우선 사용 (없으면 stderr fallback)
        if self._progress_cb:
            try:
                self._progress_cb(msg)
            except Exception:
                pass
        else:
            try:
                print(msg, file=sys.stderr)
            except (UnicodeEncodeError, OSError):
                safe = msg.encode("ascii", errors="replace").decode("ascii")
                try:
                    print(safe, file=sys.stderr)
                except Exception:
                    pass

    def _parse_json(self, text: str) -> dict:
        text = text.strip()
        # JSON 블록 추출 (```json ... ``` 감싸져 있을 수 있음 — Anthropic 자주 사용)
        if "```" in text:
            m = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
            if m:
                text = m.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            err_str = str(e)

            # "Extra data" — 첫 번째 완성된 JSON 객체만 추출 (Gemini 재시도 시 간헐 발생)
            if "Extra data" in err_str:
                decoder = json.JSONDecoder()
                obj, _ = decoder.raw_decode(text)
                if isinstance(obj, dict):
                    return obj

            # "Unterminated string" — max_tokens 초과로 응답이 잘린 경우
            # tcs 또는 features 배열에서 완성된 요소들만 추출해 부분 결과 반환
            if "Unterminated string" in err_str or "Expecting" in err_str:
                partial = self._recover_partial_json(text)
                if partial:
                    return partial
            raise

    def _recover_partial_json(self, text: str) -> dict | None:
        """잘린 JSON에서 완성된 배열 요소만 추출 (max_tokens 초과 시 응급 복구).

        {"tcs": [...]} 또는 {"features": [...]} 형식에서
        마지막 완성된 배열 요소까지만 파싱해 반환.
        """
        # 배열 시작 위치 탐색 ("tcs" or "features" 키)
        for key in ("tcs", "features"):
            m = re.search(rf'"{key}"\s*:\s*\[', text)
            if not m:
                continue
            arr_start = m.end() - 1  # '[' 위치
            # 완성된 요소 개수를 줄여가며 파싱 시도
            # 마지막 ',' 또는 '{{' 전까지 잘라서 닫기
            arr_text = text[arr_start:]
            # 역방향으로 마지막 완성된 '}' 찾기
            last_brace = arr_text.rfind("},")
            if last_brace == -1:
                last_brace = arr_text.rfind("}")
            if last_brace == -1:
                continue
            truncated = arr_text[: last_brace + 1] + "]}"
            # 앞에 키 복원
            candidate = text[: m.start()] + f'"{key}": ' + truncated
            # 앞부분이 유효한 JSON 시작인지 확인
            if not candidate.startswith("{"):
                candidate = "{" + candidate
            try:
                result = json.loads(candidate)
                if isinstance(result, dict) and key in result:
                    return result
            except json.JSONDecodeError:
                pass
        return None

    def _log(
        self,
        contract_id: str,
        provider_name: str,
        inputs: dict,
        user_msg: str,
        raw: str,
        parsed: dict,
        elapsed: float,
        input_tokens: int,
        output_tokens: int,
        model: str,
    ) -> None:
        ts = int(time.time())
        # 동시성(D55): 같은 초 + 같은 contract 동시 호출 시 파일명 충돌 방지용 시퀀스
        with self._lock:
            self._log_seq += 1
            seq = self._log_seq
        log = {
            "contract_id": contract_id,
            "provider": provider_name,
            "model": model,
            "timestamp": ts,
            "elapsed_sec": round(elapsed, 2),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "inputs": inputs,
            "user_message": user_msg,
            "raw_response": raw,
            "parsed": parsed,
        }
        log_path = self._log_dir / f"{ts}_{seq:04d}_{contract_id}.json"
        log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
