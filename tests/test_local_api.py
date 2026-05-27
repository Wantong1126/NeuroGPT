# SPDX-License-Identifier: MIT
"""Tests for the local MVP HTTP API."""
from __future__ import annotations

from modules import symptom_extractor
from ui.api import SESSION_STATES, create_app


INTERNAL_TERMS = [
    "LLM",
    "provider unavailable",
    "TimeoutError",
    "API",
    "DeepSeek",
    "JSON",
    "fallback",
    "llm_observation",
    "openai_compatible",
]


def _client():
    SESSION_STATES.clear()
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def assert_no_internal_terms(text: str) -> None:
    for term in INTERNAL_TERMS:
        assert term not in text


def test_api_chat_returns_valid_mvp_payload() -> None:
    client = _client()

    response = client.post("/api/chat", json={"message": "sudden right arm weakness and face droop"})
    data = response.get_json()

    assert response.status_code == 200
    assert data["session_id"]
    payload = data["payload"]
    assert payload["user_message"]
    assert payload["action_level"] == "emergency_now"
    assert payload["next_action_label"]
    assert "debug_metadata" in payload
    assert payload["debug_metadata"]["observation_mode_used"] == "deterministic_only"


def test_api_emergency_input_returns_emergency_now() -> None:
    client = _client()

    response = client.post("/api/chat", json={"message": "sudden right arm weakness and face droop"})
    payload = response.get_json()["payload"]

    assert payload["action_level"] == "emergency_now"
    assert payload["needs_follow_up_question"] is False
    assert payload["follow_up_question"] is None


def test_api_ambiguous_input_returns_one_follow_up_question() -> None:
    client = _client()

    response = client.post("/api/chat", json={"message": "my right hand feels weird and numb"})
    payload = response.get_json()["payload"]

    assert payload["needs_follow_up_question"] is True
    assert payload["follow_up_question"]
    assert payload["follow_up_question"].count("？") + payload["follow_up_question"].count("?") == 1


def test_api_same_session_preserves_multi_turn_state() -> None:
    client = _client()

    first = client.post("/api/chat", json={"session_id": "api-test-session", "message": "my right hand feels weak"})
    second = client.post(
        "/api/chat",
        json={"session_id": "api-test-session", "message": "it started suddenly this morning"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    payload = second.get_json()["payload"]
    assert payload["action_level"] == "emergency_now"
    assert payload["needs_follow_up_question"] is False
    assert payload["debug_metadata"]["deterministic_observation_count"] >= 1


def test_api_missing_or_failed_llm_does_not_crash_user_response(monkeypatch) -> None:
    monkeypatch.setattr(symptom_extractor, "get_provider", lambda _module: "openai_compatible")

    def fail_llm(*_args, **_kwargs):
        raise TimeoutError("provider unavailable")

    monkeypatch.setattr(symptom_extractor, "call_structured", fail_llm)
    client = _client()

    response = client.post("/api/chat", json={"message": "sudden right arm weakness and face droop"})
    payload = response.get_json()["payload"]

    assert response.status_code == 200
    assert payload["action_level"] == "emergency_now"
    assert payload["debug_metadata"]["llm_observation_status"] == "failed"
    assert payload["debug_metadata"]["llm_observation_error_type"] == "TimeoutError"
    assert_no_internal_terms(payload["user_message"])


def test_api_debug_metadata_is_separate_from_user_message() -> None:
    client = _client()

    response = client.post("/api/chat", json={"message": "sudden right arm weakness and face droop"})
    payload = response.get_json()["payload"]

    assert payload["debug_metadata"]["llm_observation_status"] == "not_configured"
    assert "not_configured" not in payload["user_message"]
    assert "deterministic_only" not in payload["user_message"]
    assert_no_internal_terms(payload["user_message"])


def test_api_reset_clears_session() -> None:
    client = _client()

    client.post("/api/chat", json={"session_id": "reset-me", "message": "my right hand feels weak"})
    assert "reset-me" in SESSION_STATES

    reset = client.post("/api/reset", json={"session_id": "reset-me"})

    assert reset.status_code == 200
    assert reset.get_json() == {"reset": True, "session_id": "reset-me"}
    assert "reset-me" not in SESSION_STATES


def test_api_rejects_blank_message() -> None:
    client = _client()

    response = client.post("/api/chat", json={"message": "   "})

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_request"
