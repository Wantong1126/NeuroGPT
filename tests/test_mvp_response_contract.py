# SPDX-License-Identifier: MIT
"""Tests for the stable MVP response payload contract."""

from __future__ import annotations

import json

from modules import symptom_extractor
from pipeline.orchestrator import run_pipeline, to_mvp_response_payload
from scripts import demo_mvp_flows


FRONTEND_FIELDS = {
    "user_message",
    "action_level",
    "concern_level",
    "next_action_label",
    "needs_follow_up_question",
    "follow_up_question",
    "caregiver_summary",
    "disclaimer",
    "guidance_snippets",
    "care_home_handoff",
    "daily_report_item",
    "debug_metadata",
}

DEBUG_FIELDS = {
    "llm_observation_status",
    "observation_mode_used",
    "llm_observation_error_type",
    "deterministic_observation_count",
    "llm_observation_count",
}

INTERNAL_TERMS = [
    "LLM",
    "provider",
    "TimeoutError",
    "API",
    "DeepSeek",
    "JSON",
    "fallback",
    "llm_observation",
    "openai_compatible",
]


def _payload_for(text: str, session_id: str = "contract"):
    state, output = run_pipeline(f"{session_id}-{abs(hash(text))}", text)
    return state, output, to_mvp_response_payload(state, output)


def assert_no_internal_terms(text: str) -> None:
    for term in INTERNAL_TERMS:
        assert term not in text


def test_mvp_payload_contains_required_frontend_and_debug_fields() -> None:
    _state, _output, payload = _payload_for(
        "sudden right arm weakness and face droop",
        "contract-emergency",
    )
    data = payload.model_dump(mode="json")

    assert FRONTEND_FIELDS <= set(data)
    assert DEBUG_FIELDS <= set(data["debug_metadata"])
    assert data["user_message"]
    assert data["next_action_label"]
    assert data["guidance_snippets"]
    assert data["care_home_handoff"]
    assert data["daily_report_item"]


def test_payload_separates_debug_metadata_from_user_message() -> None:
    _state, _output, payload = _payload_for(
        "sudden right arm weakness and face droop",
        "contract-debug-separation",
    )

    assert payload.debug_metadata.llm_observation_status == "not_configured"
    assert payload.debug_metadata.observation_mode_used == "deterministic_only"
    assert_no_internal_terms(payload.user_message)


def test_emergency_contract_has_no_follow_up_and_caregiver_summary() -> None:
    _state, _output, payload = _payload_for(
        "sudden right arm weakness and face droop",
        "contract-emergency-flow",
    )

    assert payload.action_level == "emergency_now"
    assert payload.needs_follow_up_question is False
    assert payload.follow_up_question is None
    assert payload.caregiver_summary
    assert payload.next_action_label == "联系当地急救电话或前往急诊"


def test_ambiguous_contract_has_exactly_one_follow_up_question() -> None:
    _state, _output, payload = _payload_for(
        "my right hand feels weird and numb",
        "contract-ambiguous-flow",
    )

    assert payload.needs_follow_up_question is True
    assert payload.follow_up_question
    assert payload.follow_up_question.count("？") + payload.follow_up_question.count("?") == 1
    assert payload.user_message.count("【接下来要确认】") == 1
    assert "【我只需要先确认这一点】" not in payload.user_message
    assert "【为什么要问】" not in payload.user_message
    assert "现在不把它说成诊断" not in payload.user_message


def test_llm_failure_fallback_debug_status_does_not_leak_to_user(monkeypatch) -> None:
    monkeypatch.setattr(symptom_extractor, "get_provider", lambda _module: "openai_compatible")

    def fail_llm(*_args, **_kwargs):
        raise TimeoutError("provider unavailable")

    monkeypatch.setattr(symptom_extractor, "call_structured", fail_llm)
    state, output = run_pipeline(
        "contract-llm-failure",
        "sudden right arm weakness and face droop",
    )
    payload = to_mvp_response_payload(state, output)

    assert payload.action_level == "emergency_now"
    assert payload.debug_metadata.llm_observation_status == "failed"
    assert payload.debug_metadata.llm_observation_error_type == "TimeoutError"
    assert payload.debug_metadata.observation_mode_used == "llm_failed_deterministic_available"
    assert_no_internal_terms(payload.user_message)


def test_llm_success_augmentation_contract_records_debug_counts(monkeypatch) -> None:
    monkeypatch.setattr(symptom_extractor, "get_provider", lambda _module: "openai_compatible")
    monkeypatch.setattr(symptom_extractor, "call_structured", demo_mvp_flows._llm_success)

    state, output = run_pipeline("contract-llm-success", "right hand feels wrapped")
    payload = to_mvp_response_payload(state, output)

    assert payload.debug_metadata.observation_mode_used == "llm_augmented"
    assert payload.debug_metadata.llm_observation_count > 0
    assert payload.debug_metadata.deterministic_observation_count >= 0
    assert "action_level" not in payload.user_message


def test_demo_runner_builds_payloads_without_live_api_key(capsys) -> None:
    payloads = demo_mvp_flows.run_demo_scenarios()

    assert {item["scenario"] for item in payloads} == {
        "emergency_red_flag",
        "ambiguous_sensory",
        "mild_transient",
        "chronic_memory_decline",
        "llm_failure_fallback",
        "llm_success_augmentation",
    }
    for item in payloads:
        assert FRONTEND_FIELDS <= set(item["payload"])
        assert DEBUG_FIELDS <= set(item["payload"]["debug_metadata"])
        assert_no_internal_terms(item["payload"]["user_message"])

    assert demo_mvp_flows.main() == 0
    printed = capsys.readouterr().out
    decoded = json.loads(printed)
    assert len(decoded) == 6
