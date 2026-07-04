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


FORBIDDEN_PRESENTATION_PHRASES = [
    "definitely",
    "confirmed",
    "diagnosed as",
    "确诊",
    "你得了",
    "一定是",
]


def assert_no_overclaiming(text: str) -> None:
    lowered = text.lower()
    for phrase in FORBIDDEN_PRESENTATION_PHRASES:
        assert phrase.lower() not in lowered


def assert_no_developer_clarification_wording(text: str) -> None:
    banned = [
        "【我先确认一件关键事】",
        "【为什么要问】",
        "现在不把它说成诊断",
        "【我只需要先确认这一点】",
    ]
    for phrase in banned:
        assert phrase not in text


def test_emergency_response_includes_serious_framing_and_immediate_action() -> None:
    _state, output = run_pipeline(
        "response-emergency",
        "sudden right arm weakness and face droop",
    )

    assert output.action_level == "emergency_now"
    assert output.needs_follow_up_question is False
    assert "我听到的情况" in output.user_message
    assert "请马上叫护理员过来看一下" in output.user_message
    assert "【现在怎么做】" in output.user_message
    assert "请马上叫护理员过来看一下" in output.user_message
    assert "急诊" in output.user_message or "急救" in output.user_message
    assert_no_overclaiming(output.user_message)


def test_emergency_response_does_not_delay_action_with_clarification() -> None:
    _state, output = run_pipeline(
        "response-emergency-no-question",
        "sudden right arm weakness and face droop",
    )

    assert output.action_level == "emergency_now"
    assert output.follow_up_question is None
    assert "【我只需要先确认这一点】" not in output.user_message
    assert_no_developer_clarification_wording(output.user_message)


def test_monitor_response_does_not_overmedicalize() -> None:
    _state, output = run_pipeline(
        "response-monitor",
        "weakness for years stable",
    )

    assert output.action_level != "emergency_now"
    assert "如果出现新的不舒服或明显加重，请马上告诉护理员" in output.user_message
    assert "立即拨打" not in output.user_message
    assert "高风险警讯" not in output.user_message
    assert_no_overclaiming(output.user_message)


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

    assert summary.startswith("我听到的情况\n")
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
    assert "请您再告诉我：" in output.user_message
    assert_no_developer_clarification_wording(output.user_message)
    question_section = output.user_message.split("请您再告诉我：", 1)[1]
    assert question_section


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
    assert "老人" in summary
    assert "偏一侧" in summary
    assert "还需要确认：起病时间" in summary
    assert "立即急诊/急救" in summary
    assert "时间线：" not in summary
    assert len(summary) <= 110
    assert "emergency_now" not in summary
    assert "high" not in summary


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


def test_emergency_wording_reduces_duplicate_panic_phrases() -> None:
    _state, output = run_pipeline(
        "response-duplicate-emergency",
        "sudden right arm weakness and face droop",
    )

    assert output.action_level == "emergency_now"
    assert output.user_message.count("立即") <= 2
    assert "联系当地急救电话或前往急诊" in output.user_message
    assert "给家属/医生：给家属/医生：" not in output.user_message


def test_caregiver_summary_preserves_timing_without_internal_labels() -> None:
    _state, output = run_pipeline(
        "response-caregiver-memory",
        "memory getting worse over months",
    )

    assert output.action_level == "prompt_clinical_review"
    assert output.caregiver_summary
    assert "老人" in output.caregiver_summary
    assert "发生情况：数月来逐渐变化" in output.caregiver_summary
    assert "时间线：" not in output.caregiver_summary
    assert "prompt_clinical_review" not in output.caregiver_summary
    assert "moderate" not in output.caregiver_summary
    assert len(output.caregiver_summary) <= 120


def test_patient_facing_clarification_uses_natural_uncertainty_wording() -> None:
    _state, output = run_pipeline(
        "response-natural-clarification",
        "my right hand feels weird and numb",
    )

    assert output.needs_follow_up_question is True
    assert "我听到您说my right hand feels weird and numb。" in output.user_message
    assert "请您再告诉我：" in output.user_message
    assert "【给家属/医生的话】" not in output.user_message
    assert "给家属/医生：" not in output.user_message
    assert_no_developer_clarification_wording(output.user_message)


def test_rich_lay_description_keeps_directly_present_symptom_details() -> None:
    text = "今天早上起床坐起身时突然眼前发黑，头晕，头感觉很重，缓了好久才恢复"
    _state, output = run_pipeline("response-rich-lay-description", text)

    assert "眼前发黑" in output.user_message
    assert "头晕" in output.user_message
    assert "头感觉很重" in output.user_message
    assert "起床坐起身" in output.user_message
    assert "缓了好久才恢复" in output.user_message
    assert "视力变化突然出现" not in output.user_message
    assert "时间线：" not in (output.caregiver_summary or "")
    assert "老人" in (output.caregiver_summary or "")
    assert_no_overclaiming(output.user_message)
