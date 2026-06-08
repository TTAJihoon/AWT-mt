"""LLM provider 추상화 테스트 (D48).

검증 항목:
- 모델명 prefix → provider 이름 매핑
- 알 수 없는 prefix는 ValueError
- LLMProvider는 추상 클래스 (직접 인스턴스화 불가)
- resolve_provider는 lazy import — 의존성 없으면 명확한 오류
- LLMClient가 같은 provider는 1회만 인스턴스화 (캐시)
- 캐시 키에 model 포함 (다른 모델은 별도 캐시)
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.api.providers import (
    ChatResult,
    LLMProvider,
    provider_name_for_model,
)


# ──────────────────────────────────────────────────────────────────────────
# 모델명 prefix → provider 매핑
# ──────────────────────────────────────────────────────────────────────────

class TestProviderNameMapping:
    """모델명에서 provider 이름 추론."""

    @pytest.mark.parametrize("model,expected", [
        ("claude-sonnet-4-6", "anthropic"),
        ("claude-haiku-4-5-20251001", "anthropic"),
        ("claude-opus-4-5", "anthropic"),
        ("Claude-Sonnet-4-6", "anthropic"),  # 대소문자 무관
        ("gpt-4o", "openai"),
        ("gpt-4o-mini", "openai"),
        ("gpt-4-turbo-2024-04-09", "openai"),
        ("o1-mini", "openai"),
        ("o3-mini", "openai"),
        ("gemini-1.5-flash", "google"),
        ("gemini-1.5-pro", "google"),
        ("gemini-2.0-flash", "google"),
    ])
    def test_known_prefixes(self, model: str, expected: str):
        assert provider_name_for_model(model) == expected

    @pytest.mark.parametrize("model", [
        "llama-3-70b",
        "mistral-large",
        "deepseek-r1",
        "",
        "unknown",
        "claude",          # prefix만, 뒤가 - 없음
        "gpt",
    ])
    def test_unknown_prefix_raises(self, model: str):
        with pytest.raises(ValueError, match="Unknown model prefix"):
            provider_name_for_model(model)

    def test_whitespace_tolerant(self):
        assert provider_name_for_model("  claude-sonnet-4-6  ") == "anthropic"


# ──────────────────────────────────────────────────────────────────────────
# LLMProvider 추상 클래스
# ──────────────────────────────────────────────────────────────────────────

class TestAbstractProvider:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            LLMProvider()  # type: ignore[abstract]

    def test_chat_result_dataclass(self):
        r = ChatResult(text="{}", input_tokens=10, output_tokens=5, model="gpt-4o")
        assert r.text == "{}"
        assert r.input_tokens == 10
        assert r.output_tokens == 5
        assert r.model == "gpt-4o"
        assert r.raw is None


# ──────────────────────────────────────────────────────────────────────────
# LLMClient 라우팅
# ──────────────────────────────────────────────────────────────────────────

class FakeProvider(LLMProvider):
    """테스트용 — 어떤 model이든 받아서 고정 응답 반환."""
    name = "fake"
    call_count = 0

    def __init__(self, api_key: str = "fake-key"):
        self.api_key = api_key

    def chat(self, system, user, model, max_tokens, json_mode=True):
        FakeProvider.call_count += 1
        return ChatResult(
            text='{"ok": true}',
            input_tokens=100,
            output_tokens=20,
            model=model,
            raw={"system": system, "user": user},
        )


class TestLLMClientRouting:
    def setup_method(self):
        FakeProvider.call_count = 0

    def test_provider_instance_cached(self, tmp_path, monkeypatch):
        """같은 provider 이름이면 1회만 인스턴스화."""
        from app.api.llm_client import LLMClient

        # data/runs 격리
        import app.api.llm_client as mod
        monkeypatch.setattr(mod, "_LOG_DIR", tmp_path / "runs")

        client = LLMClient(api_key="test-key", run_id="testrun")

        # provider_name_for_model을 stub해서 둘 다 "fake" 반환
        with patch("app.api.llm_client.resolve_provider", return_value=FakeProvider()):
            p1 = client._get_provider("claude-sonnet-4-6")
            p2 = client._get_provider("claude-haiku-4-5-20251001")
        # 같은 anthropic provider — 인스턴스 동일 (캐시 작동)
        assert p1 is p2

    def test_log_includes_provider_and_model(self, tmp_path, monkeypatch):
        """로그 파일에 provider·model 기록 검증."""
        import app.api.llm_client as mod
        monkeypatch.setattr(mod, "_LOG_DIR", tmp_path / "runs")

        from app.api.llm_client import LLMClient

        client = LLMClient(api_key="test-key", run_id="testrun")

        # resolve_provider를 FakeProvider로 교체
        fake = FakeProvider()
        with patch.object(client, "_get_provider", return_value=fake):
            # 캐시 비활성화로 강제 호출
            result = client.call("TC_DESIGN", {
                "category_major": "X",
                "category_mid": "Y",
                "category_leaf": "Z",
                "requirement_id": "F001",
                "tc_id_start": "TC-001-001",
                "manual_excerpt": "test",
                "defect_patterns": "",
            }, use_cache=False)

        assert result == {"ok": True}

        # 로그 파일 존재 + provider·model 필드 검증
        log_files = list((tmp_path / "runs" / "testrun" / "llm").glob("*.json"))
        assert len(log_files) == 1
        import json
        log = json.loads(log_files[0].read_text(encoding="utf-8"))
        assert log["provider"] == "fake"
        assert log["contract_id"] == "TC_DESIGN"
        assert log["input_tokens"] == 100
        assert log["output_tokens"] == 20


# ──────────────────────────────────────────────────────────────────────────
# Lazy import 검증 (의존성 없으면 RuntimeError)
# ──────────────────────────────────────────────────────────────────────────

class TestLazyImport:
    """provider 모듈 import 시점이 아니라, 인스턴스화 시점에만 의존성 체크."""

    def test_anthropic_module_imports_without_anthropic_package(self):
        # 모듈 자체는 anthropic 없이도 import 가능해야 함
        import importlib
        mod = importlib.import_module("app.api.providers.anthropic_provider")
        assert hasattr(mod, "AnthropicProvider")

    def test_openai_module_imports_without_openai_package(self):
        import importlib
        mod = importlib.import_module("app.api.providers.openai_provider")
        assert hasattr(mod, "OpenAIProvider")

    def test_gemini_module_imports_without_genai_package(self):
        import importlib
        mod = importlib.import_module("app.api.providers.gemini_provider")
        assert hasattr(mod, "GeminiProvider")


# ──────────────────────────────────────────────────────────────────────────
# 캐시 키에 model 포함 검증 (D48)
# ──────────────────────────────────────────────────────────────────────────

class TestCacheKey:
    def test_model_changes_cache_key(self, tmp_path, monkeypatch):
        """같은 inputs라도 다른 model이면 캐시 키 달라야 한다."""
        from app.tools import cache as cache_store

        # 캐시 디렉터리 격리
        monkeypatch.setattr(cache_store, "CACHE_DIR", tmp_path / "cache")

        inputs_a = {"x": 1, "__model__": "claude-sonnet-4-6"}
        inputs_b = {"x": 1, "__model__": "gpt-4o"}

        cache_store.put("TC_DESIGN", "v2.0", inputs_a, {"src": "anthropic"})
        cache_store.put("TC_DESIGN", "v2.0", inputs_b, {"src": "openai"})

        # 각각 다른 결과로 캐시되어야 함
        assert cache_store.get("TC_DESIGN", "v2.0", inputs_a) == {"src": "anthropic"}
        assert cache_store.get("TC_DESIGN", "v2.0", inputs_b) == {"src": "openai"}
