# SPDX-License-Identifier: MIT
"""Tests for deterministic elder-facing response structure."""

from __future__ import annotations

from core.observations import NormalizedObservation
from core.types import ActionLevel, CaseState, ConcernLevel, ExtractedSymptoms, Onset
from modules.response_builder import (
    build_caregiver_doctor_summary,
    build_clarification_response,
    build_key_signs_summary,
)
from modules import symptom_extractor
from pipeline.orchestrator import run_pipeline


def test_emergency_response_includes_serious_framing_and_immediate_action() -> None:
    _state, output = run_pipeline(
        "response-emergency",
        "sudden right arm weakness and face droop",
    )

    assert output.action_level == "emergency_now"
    assert output.needs_follow_up_question is False
    assert "【我目前抓到的重点】" in output.user_message
    assert "【为什么要马上动】" in output.user_message
    assert "【现在怎么做】" in output.user_message
    assert "立即" in output.user_message


def test_emergency_response_does_not_delay_action_with_clarification() -> None:
    _state, output = run_pipeline(
        "response-emergency-no-question",
        "sudden right arm weakness and face droop",
    )

    assert output.action_level == "emergency_now"
    assert output.follow_up_question is None
    assert "【我只需要先确认这一点】" not in output.user_message


def test_monitor_response_does_not_overmedicalize() -> None:
    _state, output = run_pipeline(
        "response-monitor",
        "weakness for years stable",
    )

    assert output.action_level != "emergency_now"
    assert "【为什么现在先观察】" in output.user_message
    assert "目前没有识别到明确高风险模式" in output.user_message
    assert "立即拨打" not in output.user_message


def test_key_understood_signs_are_summarized_from_observations() -> None:
    state = CaseState(
        symptoms_detected=ExtractedSymptoms(
            observations=[
                NormalizedObservation(
                    raw_text="sudden right arm weakness",
                    symptom_family="weakness",
                    signal_strength="red_flag_candidate",
                    onset="sudden",
                    laterality="one_side",
                    evidence_text="right arm weakness",
                )
            ]
        )
    )

    summary = build_key_signs_summary(state)

    assert summary.startswith("【我目前抓到的重点】")
    assert "偏一侧" in summary
    assert "无力" in summary
    assert "突然出现" in summary


def test_only_one_clarification_question_is_surfaced() -> None:
    state = CaseState(symptoms_detected=ExtractedSymptoms())
    response = build_clarification_response(
        state,
        "这个症状是什么时候开始的？是一侧还是两侧？有没有加重？",
    )

    assert response.clarification_question == "这个症状是什么时候开始的？"


def test_pipeline_surfaces_one_clarification_question_when_needed() -> None:
    _state, output = run_pipeline("response-one-question", "right hand weak")

    assert output.needs_follow_up_question is True
    assert "【我只需要先确认这一点】" in output.user_message
    question_section = output.user_message.split("【我只需要先确认这一点】", 1)[1]
    assert question_section.count("？") + question_section.count("?") == 1


def test_caregiver_doctor_summary_helper_returns_short_handoff() -> None:
    state = CaseState(
        action_level=ActionLevel.EMERGENCY_NOW,
        concern_level=ConcernLevel.HIGH,
        symptoms_detected=ExtractedSymptoms(
            onset=Onset.UNKNOWN,
            observations=[
                NormalizedObservation(
                    raw_text="right arm weakness",
                    symptom_family="weakness",
                    signal_strength="red_flag_candidate",
                    laterality="one_side",
                    evidence_text="right arm weakness",
                )
            ],
        ),
    )

    summary = build_caregiver_doctor_summary(state)

    assert summary.startswith("给家属/医生：")
    assert "偏一侧" in summary
    assert "起病时间未确认" in summary
    assert "立即急诊/急救" in summary


def test_llm_failure_metadata_is_not_exposed_to_elder_user(monkeypatch) -> None:
    monkeypatch.setattr(symptom_extractor, "get_provider", lambda _module: "openai_compatible")

    def fail_llm(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(symptom_extractor, "call_structured", fail_llm)

    state, output = run_pipeline(
        "response-no-llm-leak",
        "sudden right arm weakness and face droop",
    )

    assert state.symptoms_detected.llm_observation_status == "failed"
    assert output.action_level == "emergency_now"
    assert "LLM" not in output.user_message
    assert "RuntimeError" not in output.user_message
    assert "provider unavailable" not in output.user_message
