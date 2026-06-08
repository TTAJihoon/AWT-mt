"""Google Gemini provider 구현 (google-genai 신 SDK 기준)."""
from __future__ import annotations

from app.api.providers.base import ChatResult, LLMProvider


class GeminiProvider(LLMProvider):
    name = "google"

    def __init__(self, api_key: str):
        try:
            from google import genai
        except ImportError as e:
            raise RuntimeError(
                "Gemini provider requires 'google-genai' package. "
                "Install: pip install google-genai>=0.3.0"
            ) from e
        if not api_key:
            raise ValueError("Google API key is empty.")
        self._genai = genai
        self._client = genai.Client(api_key=api_key)

    def chat(
        self,
        system: str,
        user: str,
        model: str,
        max_tokens: int,
        json_mode: bool = True,
    ) -> ChatResult:
        from google.genai import types

        m = model.lower()
        # gemma-* 제외, gemini-* 계열은 버전 무관 모두 thinking 비활성화 대상
        _is_gemini = m.startswith("gemini-")
        _is_gemma  = m.startswith("gemma-")

        config_kwargs: dict = {"max_output_tokens": max_tokens}

        # system_instruction: gemma-* 모델은 미지원 → user 프롬프트에 병합
        if _is_gemma:
            contents = f"{system}\n\n---\n\n{user}" if system else user
        else:
            config_kwargs["system_instruction"] = system
            contents = user

        # JSON 모드: gemma-* 미지원 → 프롬프트에 JSON 요청 추가
        if json_mode and not _is_gemma:
            config_kwargs["response_mime_type"] = "application/json"
        elif json_mode and _is_gemma:
            contents += "\n\n반드시 JSON만 출력하고 다른 텍스트는 포함하지 마세요."

        # thinking_budget=0: gemini-* 전 계열 (2.x / 3.x 포함)
        # thinking 토큰이 max_output_tokens 예산을 잠식해 JSON 중간 절단되는 문제 방지
        if _is_gemini:
            try:
                config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
            except (AttributeError, TypeError):
                pass

        response = self._client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(**config_kwargs),
        )

        text = response.text or ""

        # ── 빈 응답 진단: finish_reason / safety_ratings / prompt_feedback ──
        if not text.strip():
            finish_reason = ""
            block_reason  = ""
            blocked_cats: list[str] = []
            try:
                if getattr(response, "candidates", None):
                    cand = response.candidates[0]
                    fr   = getattr(cand, "finish_reason", None)
                    finish_reason = (str(fr.name) if hasattr(fr, "name") else str(fr or "")).upper()
                    for r in (getattr(cand, "safety_ratings", None) or []):
                        if getattr(r, "blocked", False):
                            cat = getattr(r, "category", None)
                            cat_s = cat.name if hasattr(cat, "name") else str(cat or "?")
                            prob = getattr(r, "probability", None)
                            prob_s = prob.name if hasattr(prob, "name") else str(prob or "?")
                            blocked_cats.append(f"{cat_s}={prob_s}")
                pf = getattr(response, "prompt_feedback", None)
                if pf is not None:
                    br = getattr(pf, "block_reason", None)
                    block_reason = (str(br.name) if hasattr(br, "name") else str(br or "")).upper()
            except Exception:
                pass

            safety_info = ", ".join(blocked_cats) if blocked_cats else ""

            # 사유별 메시지 분류 — [TRANSIENT] 마커가 있으면 llm_client가 재시도
            if "SAFETY" in (finish_reason + " " + block_reason) or blocked_cats:
                raise RuntimeError(
                    "Gemini 안전 필터에 의해 응답이 차단되었습니다.\n"
                    f"  finish_reason: {finish_reason or '(없음)'}\n"
                    f"  block_reason: {block_reason or '(없음)'}\n"
                    f"  safety: {safety_info or '(없음)'}\n"
                    "해결: 프롬프트에서 차단 트리거가 될만한 내용을 줄이세요."
                )
            if "RECITATION" in finish_reason:
                raise RuntimeError(
                    "Gemini가 학습 데이터 인용 가능성으로 응답을 거부했습니다 (RECITATION).\n"
                    "해결: 입력 컨텐츠를 다르게 표현하거나, 다른 모델을 사용하세요."
                )
            if "MAX_TOKENS" in finish_reason:
                raise RuntimeError(
                    f"Gemini가 max_output_tokens={max_tokens}에 도달했으나 결과는 비어 있습니다.\n"
                    "해결: max_output_tokens를 늘리세요 (프롬프트 frontmatter)."
                )
            # 기타 — 일시 장애로 간주, 재시도 가능
            raise RuntimeError(
                f"[TRANSIENT] Gemini가 빈 응답을 반환했습니다 "
                f"(finish_reason={finish_reason or '(없음)'}). API 일시 장애일 수 있습니다."
            )

        # Gemini usage_metadata: prompt_token_count, candidates_token_count
        usage = response.usage_metadata
        input_tokens = getattr(usage, "prompt_token_count", 0) or 0
        output_tokens = getattr(usage, "candidates_token_count", 0) or 0

        return ChatResult(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            raw=None,  # google-genai 응답은 dict 변환 까다로움 — 디버그는 별도 처리
        )
