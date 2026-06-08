"""Anthropic Claude provider 구현."""
from __future__ import annotations

from app.api.providers.base import ChatResult, LLMProvider


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str):
        try:
            import anthropic
        except ImportError as e:
            raise RuntimeError(
                "Anthropic provider requires 'anthropic' package. "
                "Install: pip install anthropic>=0.40.0"
            ) from e
        if not api_key:
            raise ValueError("Anthropic API key is empty.")
        self._client = anthropic.Anthropic(api_key=api_key)

    def chat(
        self,
        system: str,
        user: str,
        model: str,
        max_tokens: int,
        json_mode: bool = True,
    ) -> ChatResult:
        # Anthropic은 native JSON mode가 없으므로 system prompt로 강제.
        # 기존 prompts/*.md의 system 본문이 이미 "JSON 스키마만 사용" 명시 → 추가 보강만.
        if json_mode and "JSON" not in system.upper():
            system = system + "\n\n출력은 반드시 JSON 객체로만 응답해. 자유 텍스트·설명 금지."

        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )

        text = response.content[0].text if response.content else ""
        return ChatResult(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=response.model,
            raw=response.model_dump() if hasattr(response, "model_dump") else None,
        )
