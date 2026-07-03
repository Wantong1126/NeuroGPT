# SPDX-License-Identifier: MIT
"""Tests for deterministic source-backed medical guidance cards."""

from __future__ import annotations

from modules import symptom_extractor
from modules.medical_guidance import select_guidance_cards
from pipeline.orchestrator import run_pipeline


FORBIDDEN_CLAIMS = [
    "确诊",
    "你得了",
    "一定是",
    "you have stroke",
    "diagnosed as",
    "definitely",
]


def assert_no_diagnostic_claims(text: str) -> None:
    lowered = text.lower()
    for phrase in FORBIDDEN_CLAIMS:
        assert phrase.lower() not in lowered


def assert_no_source_urls(text: str) -> None:
    assert "https://" not in text
    assert "cdc.gov" not in text
    assert "stroke.org" not in text
    assert "nice.org.uk" not in text
    assert "nimh.nih.gov" not in text


def card_ids(state) -> list[str]:
    return [card.id for card in select_guidance_cards(state)]


def test_stroke_emergency_attaches_source_backed_guidance() -> None:
    state, output = run_pipeline(
        "guidance-stroke",
        "sudden right arm weakness and face droop",
    )

    assert output.action_level == "emergency_now"
    assert "stroke_red_flags" in card_ids(state)
    assert output.guidance_snippets
    assert "为什么要关注" in output.user_message
    assert "这些变化是突然出现的，需要尽快让医护人员看一下" in output.user_message
    assert_no_diagnostic_claims(output.user_message)
    assert_no_source_urls(output.user_message)


def test_sudden_confusion_attaches_confusion_guidance() -> None:
    state, output = run_pipeline("guidance-confusion", "sudden confusion today")

    assert output.action_level == "emergency_now"
    assert "sudden_confusion" in card_ids(state)
    assert "突然变糊涂" in output.user_message
    assert_no_diagnostic_claims(output.user_message)


def test_severe_headache_emergency_attaches_headache_guidance() -> None:
    state, output = run_pipeline(
        "guidance-headache",
        "sudden worst headache with vomiting",
    )

    assert output.action_level == "emergency_now"
    assert "severe_headache" in card_ids(state)
    assert "头痛" in output.user_message
    assert "排除严重原因" in output.user_message
    assert_no_diagnostic_claims(output.user_message)


def test_fall_head_injury_red_flags_attach_head_injury_guidance() -> None:
    state, output = run_pipeline(
        "guidance-head-injury",
        "fell and hit head then lost consciousness",
    )

    assert output.action_level == "emergency_now"
    assert "fall_head_injury" in card_ids(state)
    assert "跌倒或头部受伤" in output.user_message
    assert_no_diagnostic_claims(output.user_message)


def test_suicidal_language_card_uses_narrow_phrase_detector_without_action_change() -> None:
    state, output = run_pipeline("guidance-suicide", "I want to kill myself")

    assert output.action_level == "monitor"
    assert "suicidal_language" in card_ids(state)
    assert "suicidal_language" in [card.id for card in select_guidance_cards(state)]
    # The current question-first pipeline does not render guidance until action-tier response building.
    assert "当地心理危机热线" not in output.user_message


def test_suicidal_language_guidance_renders_when_response_is_built_after_action() -> None:
    state, _output = run_pipeline("guidance-suicide-render", "I want to kill myself")
    state.needs_follow_up_question = False

    from modules.response_builder import build_response

    response = build_response(state)

    assert response.guidance_snippets
    assert "当地心理危机热线" in response.guidance_snippets[0]
    assert_no_diagnostic_claims(response.guidance_snippets[0])


def test_monitor_ambiguous_sensory_case_does_not_attach_stroke_guidance() -> None:
    state, output = run_pipeline(
        "guidance-monitor-sensory",
        "my right hand feels weird and numb",
    )

    assert output.action_level != "emergency_now"
    assert "stroke_red_flags" not in card_ids(state)
    assert "为什么要关注" not in output.user_message


def test_guidance_does_not_change_action_level() -> None:
    _state, output = run_pipeline(
        "guidance-action-stable",
        "sudden severe headache",
    )

    assert output.action_level == "emergency_now"
    assert output.guidance_snippets


def test_llm_failure_fallback_still_attaches_deterministic_guidance(monkeypatch) -> None:
    monkeypatch.setattr(symptom_extractor, "get_provider", lambda _module: "openai_compatible")

    def fail_llm(*_args, **_kwargs):
        raise TimeoutError("provider unavailable")

    monkeypatch.setattr(symptom_extractor, "call_structured", fail_llm)

    state, output = run_pipeline(
        "guidance-llm-failure",
        "sudden right arm weakness and face droop",
    )

    assert state.symptoms_detected.llm_observation_status == "failed"
    assert output.action_level == "emergency_now"
    assert "stroke_red_flags" in card_ids(state)
    assert output.guidance_snippets
    assert "provider unavailable" not in output.user_message
    assert_no_source_urls(output.user_message)


def test_rendered_guidance_is_kept_short_when_multiple_cards_match() -> None:
    _state, output = run_pipeline(
        "guidance-short-render",
        "sudden right arm weakness and worst headache",
    )

    assert output.action_level == "emergency_now"
    assert len(output.guidance_snippets) >= 2
    guidance_section = output.user_message.split("为什么要关注", 1)[1].split("\n\n", 1)[0]
    assert guidance_section.strip().count("\n") == 0
    assert_no_diagnostic_claims(guidance_section)
