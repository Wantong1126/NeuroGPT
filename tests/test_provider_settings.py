# SPDX-License-Identifier: MIT
"""Tests for non-secret provider configuration."""

from __future__ import annotations

import httpx

from core import llm as llm_client
from core.provider_settings import (
    get_provider,
    get_provider_base_url,
    get_provider_model,
)
from pipeline.orchestrator import run_pipeline


class _FakeLLMClient:
    def __init__(self) -> None:
        self.posts: list[dict] = []

    def __enter__(self) -> "_FakeLLMClient":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def post(self, url: str, *, headers: dict, json: dict) -> httpx.Response:
        self.posts.append({"url": url, "headers": headers, "json": json})
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": '{"observations": []}'}}]},
        )


def test_symptom_extractor_resolves_deepseek_provider_config() -> None:
    assert get_provider("symptom_extractor") == "openai_compatible"
    assert get_provider_base_url("symptom_extractor") == "https://api.deepseek.com/v1"
    assert get_provider_model("symptom_extractor") == "deepseek-v4-pro"


def test_elder_explanation_resolves_deepseek_provider_config() -> None:
    assert get_provider("elder_explanation_generator") == "openai_compatible"
    assert get_provider_base_url("elder_explanation_generator") == "https://api.deepseek.com/v1"
    assert get_provider_model("elder_explanation_generator") == "deepseek-v4-pro"


def test_llm_runtime_config_is_non_secret_and_env_overridable(monkeypatch) -> None:
    monkeypatch.setenv("NEUROGPT_LLM_API_KEY", "secret-test-key")
    monkeypatch.setenv("NEUROGPT_LLM_BASE_URL", "https://override.example/v1")
    monkeypatch.setenv("NEUROGPT_LLM_MODEL", "override-model")

    config = llm_client.get_runtime_config(
        model=get_provider_model("symptom_extractor"),
        base_url=get_provider_base_url("symptom_extractor"),
    )

    assert config == {
        "base_url": "https://override.example/v1",
        "model": "override-model",
        "api_key_configured": True,
    }
    assert "secret-test-key" not in repr(config)


def test_configured_model_and_base_url_are_used_without_printing_key(monkeypatch) -> None:
    fake_client = _FakeLLMClient()
    monkeypatch.setenv("NEUROGPT_LLM_API_KEY", "secret-test-key")
    monkeypatch.delenv("NEUROGPT_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("NEUROGPT_LLM_MODEL", raising=False)
    monkeypatch.setattr(llm_client.httpx, "Client", lambda timeout: fake_client)

    llm_client.call_structured(
        "extract",
        "system",
        "{}",
        model=get_provider_model("symptom_extractor"),
        base_url=get_provider_base_url("symptom_extractor"),
    )

    assert fake_client.posts[0]["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert fake_client.posts[0]["json"]["model"] == "deepseek-v4-pro"
    assert fake_client.posts[0]["headers"]["Authorization"] == "Bearer secret-test-key"


def test_missing_deepseek_api_key_falls_back_without_crashing() -> None:
    state, output = run_pipeline(
        "deepseek-missing-key-fallback",
        "sudden right arm weakness and face droop",
    )
    symptoms = state.symptoms_detected

    assert output.action_level == "emergency_now"
    assert symptoms.llm_observation_status == "failed"
    assert symptoms.llm_observation_error_type == "RuntimeError"
    assert symptoms.llm_observation_count == 0
    assert symptoms.deterministic_observation_count > 0
    assert symptoms.observation_mode_used == "llm_failed_deterministic_available"
