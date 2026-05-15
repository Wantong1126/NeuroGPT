# SPDX-License-Identifier: MIT
"""Tests for shared lay-language symptom normalization."""

from __future__ import annotations

from core.types import Laterality, Onset, Progression
from modules.symptom_normalizer import normalize_symptoms


def test_right_hand_weakness_variants_detect_weakness_and_right_side() -> None:
    for text in ["右手没力", "右手没力气"]:
        signals = normalize_symptoms(text)

        assert signals.weakness_possible is True
        assert signals.right_side_possible is True
        assert signals.laterality == Laterality.ONE_SIDE


def test_facial_asymmetry_variants_normalize_to_same_signal() -> None:
    for text in ["嘴歪", "脸不对称"]:
        signals = normalize_symptoms(text)

        assert signals.facial_asymmetry_possible is True
        assert signals.laterality == Laterality.ONE_SIDE


def test_half_body_numbness_detects_sensory_and_one_sided_signal() -> None:
    signals = normalize_symptoms("半边身子麻")

    assert signals.sensory_possible is True
    assert signals.one_sided_possible is True
    assert signals.laterality == Laterality.ONE_SIDE


def test_non_neurological_expression_request_is_not_speech_language_symptom() -> None:
    signals = normalize_symptoms("我不知道怎么表达这个症状")

    assert signals.non_neurological_expression_request is True
    assert signals.speech_language_possible is False
    assert signals.word_finding_possible is False


def test_chronic_stable_weakness_normalizes_course() -> None:
    signals = normalize_symptoms("这几年一直没力但没有加重")

    assert signals.weakness_possible is True
    assert signals.onset == Onset.CHRONIC
    assert signals.progression == Progression.STABLE


def test_gradual_memory_decline_normalizes_cognitive_course() -> None:
    signals = normalize_symptoms("老人这几个月记忆越来越差")

    assert signals.memory_cognitive_possible is True
    assert signals.onset == Onset.GRADUAL
    assert signals.progression == Progression.WORSENING
