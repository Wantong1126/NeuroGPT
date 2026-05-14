# SPDX-License-Identifier: MIT
"""Regression tests for speech/language action-tier alignment."""

from __future__ import annotations

from modules.symptom_extractor import extract_symptoms
from pipeline.orchestrator import run_pipeline


SPEECH_ONSET_QUESTION = "这个说话/表达困难是突然出现的吗？大概从什么时候开始？"


def test_sudden_chinese_speech_with_one_sided_weakness_is_emergency() -> None:
    _state, output = run_pipeline("speech-align-cn-emergency", "我妈今天突然说话不清，右手没力")

    assert output.needs_follow_up_question is False
    assert output.concern_level == "high"
    assert output.action_level == "emergency_now"


def test_unknown_onset_speech_language_difficulty_asks_focused_followup() -> None:
    _state, output = run_pipeline("speech-align-cn-followup", "我爸最近表达有点困难")

    assert output.needs_follow_up_question is True
    assert output.follow_up_question == SPEECH_ONSET_QUESTION
    assert output.action_level != "emergency_now"


def test_uncertain_how_to_describe_symptom_is_not_neurological_speech() -> None:
    symptoms = extract_symptoms("我不知道怎么表达这个症状")

    assert "speech" not in symptoms.symptom_type
    assert symptoms.red_flags.slurred_speech is False
    assert symptoms.word_finding_difficulty is False
    assert symptoms.red_flags.stroke_beFAST is False


def test_chronic_slow_speech_without_acute_red_flags_is_not_emergency() -> None:
    _state, output = run_pipeline("speech-align-cn-chronic", "老人这几年说话越来越慢")

    assert output.needs_follow_up_question is False
    assert output.concern_level == "moderate"
    assert output.action_level == "same_day_review"


def test_sudden_english_word_output_problem_with_facial_droop_is_emergency() -> None:
    _state, output = run_pipeline(
        "speech-align-en-emergency",
        "She suddenly cannot get words out and one side of her face looks droopy",
    )

    assert output.needs_follow_up_question is False
    assert output.concern_level == "high"
    assert output.action_level == "emergency_now"
