"""LLM Provider 추상화 (D48).

모델명 prefix에 따라 적절한 provider를 반환한다:
    claude-* → AnthropicProvider
    gpt-*, o1-*, o3-* → OpenAIProvider
    gemini-*, gemma-* → GeminiProvider

상세 설계: doc/07-llm-providers.md
"""
from __future__ import annotations

from app.api.providers.base import ChatResult, LLMProvider

__all__ = ["ChatResult", "LLMProvider", "resolve_provider", "provider_name_for_model"]


def provider_name_for_model(model: str) -> str:
    """모델명 prefix → provider 이름 (raise on unknown)."""
    m = model.lower().strip()
    if m.startswith("claude-"):
        return "anthropic"
    if m.startswith("gpt-") or m.startswith("o1-") or m.startswith("o3-"):
        return "openai"
    if m.startswith("gemini-") or m.startswith("gemma-"):
        return "google"
    raise ValueError(
        f"Unknown model prefix: {model!r}. "
        "Expected claude-*, gpt-*, o1-*, o3-*, or gemini-*."
    )


def resolve_provider(model: str, api_key: str) -> LLMProvider:
    """모델명에 맞는 provider 인스턴스 생성. lazy import로 의존성 누락 시 명확한 오류."""
    name = provider_name_for_model(model)
    if name == "anthropic":
        from app.api.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(api_key=api_key)
    if name == "openai":
        from app.api.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(api_key=api_key)
    if name == "google":
        from app.api.providers.gemini_provider import GeminiProvider
        return GeminiProvider(api_key=api_key)
    raise ValueError(f"Unsupported provider: {name}")
