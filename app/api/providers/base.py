"""LLM Provider 공통 인터페이스 (D38 stateless · D48 추상화).

모든 provider 구현체는 LLMProvider를 상속하고 chat()을 구현해야 한다.
다중 턴 인터페이스는 의도적으로 노출하지 않는다 — D38(stateless) 강제.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ChatResult:
    """provider 응답 정규화 결과."""
    text: str               # 응답 본문 (json_mode=True 시 JSON 문자열)
    input_tokens: int
    output_tokens: int
    model: str              # 실제 응답한 모델명 (사용자 지정과 동일 또는 alias 해소 후)
    raw: dict | None = None # provider 원본 응답 (디버그 목적)


class LLMProvider(ABC):
    """Provider 공통 추상 인터페이스."""

    name: str = "abstract"  # 구현체에서 override ("anthropic" | "openai" | "google")

    @abstractmethod
    def chat(
        self,
        system: str,
        user: str,
        model: str,
        max_tokens: int,
        json_mode: bool = True,
    ) -> ChatResult:
        """단일 stateless chat 호출.

        Args:
            system: System prompt (역할·출력 형식 지시)
            user: User message (실제 작업 내용)
            model: 모델명 (예: claude-sonnet-4-6, gpt-4o, gemini-1.5-pro)
            max_tokens: 출력 토큰 상한
            json_mode: True면 JSON 응답 강제 (provider별 방식 차이는 내부 처리)

        Returns:
            ChatResult: 정규화된 응답 + 토큰 사용량 + 디버그용 원본
        """
        raise NotImplementedError
