# SPDX-License-Identifier: MIT
"""End-to-end MVP product scenario regressions for NeuroGPT."""

from __future__ import annotations

from modules import symptom_extractor
from pipeline.orchestrator import run_pipeline


DIAGNOSIS_CLAIMS = [
    "you have stroke",
    "this is definitely",
    "diagnosed as",
    "确诊",
    "你得了",
]

INTERNAL_LLM_TERMS = [
    "LLM",
    "TimeoutError",
    "provider unavailable",
    "llm_observation",
    "openai_compatible",
]


def _run(text: str, session_id: str = "product-scenario", state=None):
    return run_pipeline(f"{session_id}-{abs(hash(text))}", text, state)


def assert_no_diagnosis_claim(text: str) -> None:
    lowered = text.lower()
    for phrase in DIAGNOSIS_CLAIMS:
        assert phrase.lower() not in lowered


def assert_no_internal_llm_leak(text: str) -> None:
    for phrase in INTERNAL_LLM_TERMS:
        assert phrase not in text


def assert_caregiver_summary_exists(output) -> None:
    assert output.caregiver_summary
    assert output.caregiver_summary.strip()


def assert_one_question(text: str) -> None:
    assert text.count("？") + text.count("?") == 1


def test_clear_emergency_red_flag_should_not_wait_for_clarification() -> None:
    state, output = _run(
        "sudden right arm weakness and face droop",
        "product-emergency",
    )

    assert output.action_level == "emergency_now"
    assert output.needs_follow_up_question is False
    assert output.follow_up_question is None
    assert "【我目前抓到的重点】" in output.user_message
    assert "【现在怎么做】" in output.user_message
    assert "立即" in output.user_message
    assert "急诊" in output.user_message or "急救" in output.user_message
    assert "无力" in output.user_message
    assert "面部歪斜" in output.user_message
    assert_caregiver_summary_exists(output)
    assert state.caregiver_summary
    assert_no_diagnosis_claim(output.user_message)


def test_ambiguous_one_sided_sensory_complaint_asks_one_question() -> None:
    _state, output = _run(
        "my right hand feels weird and numb",
        "product-ambiguous-sensory",
    )

    assert output.action_level != "emergency_now"
    assert output.needs_follow_up_question is True
    assert "【我只需要先确认这一点】" in output.user_message
    assert_one_question(output.user_message)
    assert "偏一侧" in output.user_message
    assert "麻木" in output.user_message
    assert "立即拨打" not in output.user_message
    assert_caregiver_summary_exists(output)
    assert_no_diagnosis_claim(output.user_message)


def test_mild_transient_symptom_uses_monitor_safety_net_style() -> None:
    _state, output = _run(
        "suddenly both sides felt numb after sitting but it went away",
        "product-mild-transient",
    )

    assert output.action_level == "monitor"
    assert output.needs_follow_up_question is False
    assert "【为什么现在先观察】" in output.user_message
    assert "目前没有识别到明确高风险模式" in output.user_message
    assert "如果加重应尽快就医" in output.user_message or "需要升级处理" in output.user_message
    assert "立即拨打" not in output.user_message
    assert_caregiver_summary_exists(output)
    assert_no_diagnosis_claim(output.user_message)


def test_chronic_progressive_memory_concern_encourages_clinical_review() -> None:
    _state, output = _run(
        "memory getting worse over months",
        "product-chronic-memory",
    )

    assert output.action_level == "prompt_clinical_review"
    assert output.needs_follow_up_question is False
    assert output.action_level != "emergency_now"
    assert "【需要重视】" in output.user_message
    assert "尽快" in output.user_message
    assert "记忆" in output.user_message or "认知" in output.user_message
    assert_caregiver_summary_exists(output)
    assert "memory getting worse over months" in output.caregiver_summary
    assert "prompt_clinical_review" not in output.caregiver_summary
    assert "moderate" not in output.caregiver_summary
    assert_no_diagnosis_claim(output.user_message)


def test_llm_failure_should_not_block_deterministic_safety(monkeypatch) -> None:
    monkeypatch.setattr(symptom_extractor, "get_provider", lambda _module: "openai_compatible")

    def fail_llm(*_args, **_kwargs):
        raise TimeoutError("provider unavailable")

    monkeypatch.setattr(symptom_extractor, "call_structured", fail_llm)

    state, output = _run(
        "sudden right arm weakness and face droop",
        "product-llm-failure",
    )

    assert output.action_level == "emergency_now"
    assert state.symptoms_detected.llm_observation_status == "failed"
    assert state.symptoms_detected.llm_observation_error_type == "TimeoutError"
    assert state.symptoms_detected.observation_mode_used == "llm_failed_deterministic_available"
    assert_no_internal_llm_leak(output.user_message)
    assert_no_diagnosis_claim(output.user_message)


def test_llm_success_augments_observations_without_controlling_action(monkeypatch) -> None:
    monkeypatch.setattr(symptom_extractor, "get_provider", lambda _module: "openai_compatible")
    monkeypatch.setattr(
        symptom_extractor,
        "call_structured",
        lambda *_args, **_kwargs: {
            "action_level": "emergency_now",
            "concern_level": "high",
            "observations": [
                {
                    "raw_text": "right hand feels wrapped",
                    "symptom_family": "sensory",
                    "signal_strength": "possible",
                    "onset": "unknown",
                    "duration_text": "",
                    "duration_category": "unknown",
                    "laterality": "one_side",
                    "progression": "unknown",
                    "severity_qualifier": "unknown",
                    "transient_or_resolved": False,
                    "associated_red_flags": [],
                    "evidence_text": "right hand feels wrapped",
                    "confidence": 0.9,
                }
            ],
        },
    )

    state, output = _run(
        "right hand feels wrapped",
        "product-llm-success",
    )

    assert state.symptoms_detected.observation_mode_used == "llm_augmented"
    assert state.symptoms_detected.llm_observation_count > 0
    assert any(obs.symptom_family == "sensory" for obs in state.symptoms_detected.observations)
    assert output.action_level != "emergency_now"
    assert "麻木" in output.user_message or "感觉异常" in output.user_message
    assert "action_level" not in output.user_message
    assert "concern_level" not in output.user_message
    assert_no_diagnosis_claim(output.user_message)


def test_multi_turn_clarification_flow_updates_action_and_metadata() -> None:
    state, first_output = _run(
        "my right hand feels weak",
        "product-multiturn",
    )

    assert first_output.needs_follow_up_question is True
    assert first_output.action_level == "monitor"
    assert_one_question(first_output.user_message)
    assert_caregiver_summary_exists(first_output)

    state, second_output = run_pipeline(
        "product-multiturn",
        "it started suddenly this morning",
        state,
    )

    assert state.turn_count == 2
    assert state.symptoms_detected.onset.value == "sudden"
    assert second_output.needs_follow_up_question is False
    assert second_output.action_level == "emergency_now"
    assert "【我目前抓到的重点】" in second_output.user_message
    assert_caregiver_summary_exists(second_output)
    assert state.symptoms_detected.llm_observation_count == 0
    assert state.symptoms_detected.deterministic_observation_count == 1
    assert state.symptoms_detected.observation_mode_used == "deterministic_only"
    assert_no_diagnosis_claim(second_output.user_message)
