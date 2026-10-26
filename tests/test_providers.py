"""Tests for the LLM providers abstraction and multi-provider API key compatibility layer."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from crack.config import DEFAULT_SETTINGS, Settings
from crack.providers import (
    PROVIDERS,
    call_openai_compatible,
    check_credentials,
    create_client,
    normalize_backend_name,
    resolve_api_key,
    resolve_api_key_name,
    resolve_backend,
    resolve_base_url,
    resolve_model,
)


class TestProviderRegistry:
    def test_major_providers_registered(self) -> None:
        expected = {
            "gemini",
            "anthropic",
            "openai",
            "deepseek",
            "groq",
            "mistral",
            "dashscope",
            "moonshot",
            "zhipu",
            "siliconflow",
            "compatible",
        }
        assert expected.issubset(set(PROVIDERS.keys()))

    def test_alias_normalization(self) -> None:
        assert normalize_backend_name("qwen") == "dashscope"
        assert normalize_backend_name("kimi") == "moonshot"
        assert normalize_backend_name("glm") == "zhipu"
        assert normalize_backend_name("claude") == "anthropic"
        assert normalize_backend_name("google") == "gemini"
        assert normalize_backend_name("custom") == "compatible"
        assert normalize_backend_name("openai") == "openai"


class TestBackendResolution:
    def test_explicit_backend_returned(self) -> None:
        assert resolve_backend("openai") == "openai"
        assert resolve_backend("deepseek") == "deepseek"
        assert resolve_backend("qwen") == "dashscope"

    def test_auto_detection_with_openai_key(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-mock-openai"}, clear=True):
            assert resolve_backend("auto") == "openai"

    def test_auto_detection_with_deepseek_key(self) -> None:
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-mock-deepseek"}, clear=True):
            assert resolve_backend("auto") == "deepseek"

    def test_auto_detection_fallback_to_gemini(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            assert resolve_backend("auto") == "gemini"


class TestApiKeyResolution:
    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_preflight_rejects_missing_or_blank_key(self, value):
        with patch.dict(os.environ, {} if value is None else {"OPENAI_API_KEY": value}, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY not set"):
                check_credentials("openai")

    def test_preflight_accepts_generic_fallback_without_network(self):
        with patch.dict(os.environ, {"LLM_API_KEY": "offline-test-key"}, clear=True):
            check_credentials("openai")

    def test_resolve_api_key_name(self) -> None:
        assert resolve_api_key_name("openai") == "OPENAI_API_KEY"
        assert resolve_api_key_name("deepseek") == "DEEPSEEK_API_KEY"
        assert resolve_api_key_name("gemini") == "GEMINI_API_KEY"
        assert resolve_api_key_name("anthropic") == "ANTHROPIC_API_KEY"
        assert resolve_api_key_name("dashscope") == "DASHSCOPE_API_KEY"
        assert resolve_api_key_name("moonshot") == "MOONSHOT_API_KEY"

    def test_resolve_api_key_from_env(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-123"}):
            val, name = resolve_api_key("openai")
            assert val == "test-key-123"
            assert name == "OPENAI_API_KEY"

    def test_resolve_api_key_from_settings(self) -> None:
        settings = Settings(DEEPSEEK_API_KEY="settings-key-abc")
        val, name = resolve_api_key("deepseek", settings)
        assert val == "settings-key-abc"
        assert name == "DEEPSEEK_API_KEY"

    def test_resolve_api_key_alternative_env(self) -> None:
        with patch.dict(os.environ, {"QWEN_API_KEY": "qwen-test-key"}, clear=True):
            val, name = resolve_api_key("dashscope")
            assert val == "qwen-test-key"
            assert name == "QWEN_API_KEY"

    def test_resolve_api_key_generic_fallback(self) -> None:
        with patch.dict(os.environ, {"LLM_API_KEY": "generic-key"}, clear=True):
            val, name = resolve_api_key("deepseek")
            assert val == "generic-key"
            assert name == "LLM_API_KEY"

    def test_missing_api_key_raises_in_create_client(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY not set"):
                create_client("openai", settings=DEFAULT_SETTINGS)


class TestBaseUrlResolution:
    def test_deepseek_default_base_url(self) -> None:
        assert resolve_base_url("deepseek") == "https://api.deepseek.com"

    def test_openai_default_base_url_is_none(self) -> None:
        # None tells the openai SDK to use official default
        assert resolve_base_url("openai") is None

    def test_custom_base_url_via_settings(self) -> None:
        settings = Settings(OPENAI_BASE_URL="http://localhost:11434/v1")
        assert resolve_base_url("openai", settings) == "http://localhost:11434/v1"

    def test_custom_base_url_via_env(self) -> None:
        with patch.dict(os.environ, {"DEEPSEEK_BASE_URL": "https://custom.deepseek.proxy"}):
            assert resolve_base_url("deepseek") == "https://custom.deepseek.proxy"


class TestModelResolution:
    def test_default_models(self) -> None:
        assert resolve_model("openai", "L4", DEFAULT_SETTINGS) == "gpt-6-luna"
        assert resolve_model("openai", "L5", DEFAULT_SETTINGS) == "gpt-6-luna"
        assert resolve_model("openai", "L7", DEFAULT_SETTINGS) == "gpt-6-luna"
        assert resolve_model("openai", "L8", DEFAULT_SETTINGS) == "gpt-6-luna"
        assert resolve_model("deepseek", "L4", DEFAULT_SETTINGS) == "deepseek-chat"
        assert resolve_model("deepseek", "L5", DEFAULT_SETTINGS) == "deepseek-chat"
        assert resolve_model("deepseek", "L7", DEFAULT_SETTINGS) == "deepseek-chat"
        assert resolve_model("deepseek", "L8", DEFAULT_SETTINGS) == "deepseek-chat"

    def test_explicit_override_in_settings(self) -> None:
        settings = Settings(L5_MODEL="custom-finetuned-l5")
        assert resolve_model("openai", "L5", settings) == "custom-finetuned-l5"
        assert resolve_model("deepseek", "L5", settings) == "custom-finetuned-l5"


class TestCallOpenAICompatible:
    def test_l4_openai_sends_strict_contract_and_compatible_keeps_json_mode(self):
        from crack.l4_anchoring import _call_openai_l4
        from crack.validation import L4_RESPONSE_FIELDS
        client = MagicMock()
        choice = MagicMock()
        choice.finish_reason = "stop"
        choice.message.refusal = None
        choice.message.content = '{}'
        client.chat.completions.create.return_value = MagicMock(choices=[choice])
        _call_openai_l4("prompt", "openai", DEFAULT_SETTINGS, client)
        fmt = client.chat.completions.create.call_args.kwargs["response_format"]
        assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True
        schema = fmt["json_schema"]["schema"]
        assert set(schema["required"]) == set(schema["properties"]) == L4_RESPONSE_FIELDS
        assert schema["additionalProperties"] is False
        _call_openai_l4("prompt", "deepseek", DEFAULT_SETTINGS, client)
        assert client.chat.completions.create.call_args.kwargs["response_format"] == {"type": "json_object"}

    def test_strict_schema_rejection_does_not_downgrade(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("unsupported response_format json_schema")
        with pytest.raises(RuntimeError, match="unsupported response_format"):
            call_openai_compatible(client, "test", "prompt", response_schema={"type": "object"})
        assert client.chat.completions.create.call_count == 1

    def test_parameter_compatibility_retry_preserves_strict_schema(self):
        client = MagicMock()
        choice = MagicMock()
        choice.finish_reason = "stop"
        choice.message.refusal = None
        choice.message.content = '{}'
        client.chat.completions.create.side_effect = [
            RuntimeError("unsupported temperature"), MagicMock(choices=[choice]),
        ]
        call_openai_compatible(client, "test", "prompt", response_schema={"type": "object"})
        calls = client.chat.completions.create.call_args_list
        assert len(calls) == 2
        assert calls[0].kwargs["response_format"] == calls[1].kwargs["response_format"]
        assert "temperature" not in calls[1].kwargs

    def test_successful_call_extracts_json(self) -> None:
        client = MagicMock()
        choice = MagicMock()
        choice.finish_reason = "stop"
        choice.message.refusal = None
        choice.message.content = '{"score": 0.85, "verdict": "PASS"}'
        client.chat.completions.create.return_value = MagicMock(choices=[choice])

        parsed, retries, fallback = call_openai_compatible(
            client=client,
            model="deepseek-chat",
            prompt_text="Score this joke",
            required_keys=frozenset({"score", "verdict"}),
        )

        assert parsed == {"score": 0.85, "verdict": "PASS"}
        assert retries == 0
        assert fallback is False

    def test_retry_on_parse_failure_succeeds(self) -> None:
        client = MagicMock()
        bad_choice = MagicMock()
        bad_choice.finish_reason = "stop"
        bad_choice.message.refusal = None
        bad_choice.message.content = "Invalid non-json output"
        good_choice = MagicMock()
        good_choice.finish_reason = "stop"
        good_choice.message.refusal = None
        good_choice.message.content = '{"score": 0.9}'

        client.chat.completions.create.side_effect = [
            MagicMock(choices=[bad_choice]),
            MagicMock(choices=[good_choice]),
        ]

        parsed, retries, fallback = call_openai_compatible(
            client=client,
            model="gpt-4o-mini",
            prompt_text="Test prompt",
            required_keys=frozenset({"score"}),
        )

        assert parsed == {"score": 0.9}
        assert client.chat.completions.create.call_count == 2


class TestLoadDotenv:
    def test_load_dotenv_from_file(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text(
            "# Comment line\n"
            "TEST_KEY_1=value1\n"
            "export TEST_KEY_2=\"value2 with spaces\"\n"
            "TEST_KEY_3='value3' # inline comment\n"
            "TEST_KEY_4=value4 # comment\n",
            encoding="utf-8",
        )
        from crack.providers import load_dotenv

        with patch.dict(os.environ, {}, clear=True):
            assert load_dotenv(env_file) is True
            assert os.environ.get("TEST_KEY_1") == "value1"
            assert os.environ.get("TEST_KEY_2") == "value2 with spaces"
            assert os.environ.get("TEST_KEY_3") == "value3"
            assert os.environ.get("TEST_KEY_4") == "value4"

    def test_load_dotenv_does_not_overwrite_existing(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING_KEY=new_val\n", encoding="utf-8")
        from crack.providers import load_dotenv

        with patch.dict(os.environ, {"EXISTING_KEY": "original_val"}, clear=True):
            load_dotenv(env_file)
            assert os.environ.get("EXISTING_KEY") == "original_val"
