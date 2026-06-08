"""OpenAI GPT provider 구현."""
from __future__ import annotations

from app.api.providers.base import ChatResult, LLMProvider


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str):
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError(
                "OpenAI provider requires 'openai' package. "
                "Install: pip install openai>=1.50.0"
            ) from e
        if not api_key:
            raise ValueError("OpenAI API key is empty.")
        self._OpenAI = OpenAI
        self._client = OpenAI(api_key=api_key)

    @staticmethod
    def _uses_completion_tokens(model: str) -> bool:
        """이 모델이 max_completion_tokens를 요구하는지 판단.

        GPT-5 계열 및 추론 모델(o1/o3/o4)은 max_tokens를 거부하고
        max_completion_tokens만 허용한다. gpt-4 계열은 max_tokens 사용.
        """
        m = model.lower()
        return (
            m.startswith("gpt-5")
            or m.startswith("o1")
            or m.startswith("o3")
            or m.startswith("o4")
        )

    def chat(
        self,
        system: str,
        user: str,
        model: str,
        max_tokens: int,
        json_mode: bool = True,
    ) -> ChatResult:
        # OpenAI: native JSON mode 사용 (response_format)
        # 단, json_mode 사용 시 system 또는 user 메시지에 "json" 단어가 포함되어야 함 (API 요구사항)
        if json_mode:
            if "json" not in (system + user).lower():
                system = system + "\n\nReturn the response as a JSON object."

        kwargs: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        # 모델별 토큰 한도 파라미터 선택 (GPT-5/o-series는 max_completion_tokens)
        token_param = (
            "max_completion_tokens"
            if self._uses_completion_tokens(model)
            else "max_tokens"
        )
        kwargs[token_param] = max_tokens

        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as e:
            # 파라미터 이름 불일치(400) 시 반대 파라미터로 1회 자동 폴백
            #  - 신규 모델: max_tokens 거부 → max_completion_tokens
            #  - 구형 모델: max_completion_tokens 거부 → max_tokens
            err = str(e)
            if "max_completion_tokens" in err or "max_tokens" in err:
                alt = ("max_completion_tokens"
                       if token_param == "max_tokens" else "max_tokens")
                kwargs.pop(token_param, None)
                kwargs[alt] = max_tokens
                response = self._client.chat.completions.create(**kwargs)
            else:
                raise

        choice = response.choices[0]
        text = choice.message.content or ""
        return ChatResult(
            text=text,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            model=response.model,
            raw=response.model_dump() if hasattr(response, "model_dump") else None,
        )
