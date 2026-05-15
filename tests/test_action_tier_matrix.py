# SPDX-License-Identifier: MIT
"""Action-tier matrix tests for normalized symptom families."""

from __future__ import annotations

from modules.symptom_extractor import extract_symptoms
from pipeline.orchestrator import run_pipeline


SPEECH_ONSET_QUESTION = "这个说话/表达困难是突然出现的吗？大概从什么时候开始？"


def run_text(text: str):
    return run_pipeline(f"matrix-{abs(hash(text))}", text)


def test_vague_weakness_asks_missing_onset_or_laterality_followup() -> None:
    _state, output = run_text("老人最近没力")

    assert output.needs_follow_up_question is True
    assert "什么时候" in (output.follow_up_question or "")
    assert "一侧" in (output.follow_up_question or "")
    assert output.action_level != "emergency_now"


def test_chronic_stable_weakness_is_not_emergency() -> None:
    _state, output = run_text("这几年一直没力但没有加重")

    assert output.needs_follow_up_question is False
    assert output.action_level != "emergency_now"


def test_sudden_facial_asymmetry_is_emergency() -> None:
    _state, output = run_text("老人突然嘴歪")

    assert output.needs_follow_up_question is False
    assert output.concern_level == "high"
    assert output.action_level == "emergency_now"


def test_unclear_onset_facial_asymmetry_asks_onset_followup() -> None:
    _state, output = run_text("老人脸不对称")

    assert output.needs_follow_up_question is True
    assert "什么时候" in (output.follow_up_question or "")
    assert output.action_level != "emergency_now"


def test_unclear_onset_one_sided_numbness_asks_onset_followup() -> None:
    _state, output = run_text("半边身子麻")

    assert output.needs_follow_up_question is True
    assert "什么时候" in (output.follow_up_question or "")
    assert output.action_level != "emergency_now"


def test_sudden_confusion_or_not_recognizing_family_is_emergency() -> None:
    for text in ["老人突然糊涂", "老人突然不认人"]:
        _state, output = run_text(text)

        assert output.needs_follow_up_question is False
        assert output.concern_level == "high"
        assert output.action_level == "emergency_now"


def test_vague_recent_confusion_asks_onset_or_progression_followup() -> None:
    _state, output = run_text("老人最近有点糊涂")

    assert output.needs_follow_up_question is True
    question = output.follow_up_question or ""
    assert "突然" in question
    assert "加重" in question
    assert output.action_level != "emergency_now"


def test_gradual_memory_decline_maps_to_prompt_clinical_review() -> None:
    _state, output = run_text("老人这几个月记忆越来越差")

    assert output.needs_follow_up_question is False
    assert output.concern_level == "moderate"
    assert output.action_level == "prompt_clinical_review"


def test_speech_language_alignment_is_preserved() -> None:
    cases = [
        ("我妈今天突然说话不清，右手没力", False, "emergency_now"),
        ("我爸最近表达有点困难", True, "monitor"),
        ("老人这几年说话越来越慢", False, "same_day_review"),
        (
            "She suddenly cannot get words out and one side of her face looks droopy",
            False,
            "emergency_now",
        ),
    ]

    for text, asks_question, action_level in cases:
        _state, output = run_text(text)

        assert output.needs_follow_up_question is asks_question
        assert output.action_level == action_level
        if text == "我爸最近表达有点困难":
            assert output.follow_up_question == SPEECH_ONSET_QUESTION


def test_expression_uncertainty_is_not_neurological_speech() -> None:
    symptoms = extract_symptoms("我不知道怎么表达这个症状")

    assert "speech" not in symptoms.symptom_type
    assert symptoms.red_flags.slurred_speech is False
    assert symptoms.word_finding_difficulty is False
    assert symptoms.red_flags.stroke_beFAST is False
