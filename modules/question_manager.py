# SPDX-License-Identifier: MIT
"""
NeuroGPT v2 - Question Manager
Decides whether to ask a follow-up question and generates it.
"""

from __future__ import annotations

from core.types import CaseState, ExtractedSymptoms, Onset, Progression


SPEECH_ONSET_QUESTION = "这个说话/表达困难是突然出现的吗？大概从什么时候开始？"
FOCAL_ONSET_QUESTION = "这个症状是突然出现的吗？大概从什么时候开始？是一侧还是两侧？"
CONFUSION_ONSET_QUESTION = "这种糊涂/意识变化是突然出现的吗？最近有没有加重？"
GENERAL_ONSET_QUESTION = "这个症状是从什么时候开始的？是突然发生的，还是慢慢出现的？"
PROGRESSION_QUESTION = "最近这个症状有没有加重？比如更频繁，或者更严重？"


def _has_speech_language_symptom(symptoms: ExtractedSymptoms) -> bool:
    return (
        symptoms.red_flags.slurred_speech
        or symptoms.word_finding_difficulty
        or "speech" in symptoms.symptom_type
    )


def _has_weakness_symptom(symptoms: ExtractedSymptoms) -> bool:
    return symptoms.red_flags.weakness_one_side or (
        "motor" in symptoms.symptom_type and not symptoms.tremor_present
    )


def _has_facial_asymmetry_symptom(symptoms: ExtractedSymptoms) -> bool:
    return symptoms.red_flags.facial_droop


def _has_sensory_symptom(symptoms: ExtractedSymptoms) -> bool:
    return symptoms.red_flags.focal_numbness or "sensory" in symptoms.symptom_type


def _has_focal_or_stroke_family_symptom(symptoms: ExtractedSymptoms) -> bool:
    rf = symptoms.red_flags
    return any(
        [
            _has_weakness_symptom(symptoms),
            _has_facial_asymmetry_symptom(symptoms),
            _has_sensory_symptom(symptoms),
            _has_speech_language_symptom(symptoms),
            rf.vision_loss,
            rf.gait_imbalance,
        ]
    )


def _has_confusion_or_awareness_symptom(symptoms: ExtractedSymptoms) -> bool:
    rf = symptoms.red_flags
    return (
        rf.acute_confusion
        or rf.loss_of_consciousness
        or symptoms.disorientation
        or symptoms.memory_concern
    )


def _has_immediate_emergency_without_followup(symptoms: ExtractedSymptoms) -> bool:
    rf = symptoms.red_flags
    has_speech_language_symptom = _has_speech_language_symptom(symptoms)
    return any(
        [
            rf.seizure,
            rf.loss_of_consciousness,
            symptoms.onset == Onset.SUDDEN and _has_focal_or_stroke_family_symptom(symptoms),
            symptoms.onset == Onset.SUDDEN and rf.acute_confusion,
            symptoms.onset == Onset.SUDDEN and rf.severe_headache,
            has_speech_language_symptom
            and any([rf.weakness_one_side, rf.facial_droop, rf.focal_numbness]),
            rf.head_injury and any([rf.acute_confusion, rf.seizure, rf.loss_of_consciousness]),
        ]
    )


def _should_skip_laterality_question(symptoms: ExtractedSymptoms) -> bool:
    if symptoms.onset == Onset.CHRONIC and symptoms.progression == Progression.STABLE:
        return True
    if _has_speech_language_symptom(symptoms):
        return True
    if symptoms.memory_concern or symptoms.disorientation:
        return True
    return False


def decide_question(state: CaseState) -> str | None:
    """Return the single most useful follow-up question, or None."""
    symptoms: ExtractedSymptoms = state.symptoms_detected

    # Do not block source-backed obvious emergencies behind more questions.
    if _has_immediate_emergency_without_followup(symptoms):
        return None

    if _has_speech_language_symptom(symptoms) and symptoms.onset == Onset.UNKNOWN:
        return SPEECH_ONSET_QUESTION

    if _has_confusion_or_awareness_symptom(symptoms) and symptoms.onset == Onset.UNKNOWN:
        return CONFUSION_ONSET_QUESTION

    if _has_focal_or_stroke_family_symptom(symptoms) and symptoms.onset == Onset.UNKNOWN:
        return FOCAL_ONSET_QUESTION

    if symptoms.onset == Onset.UNKNOWN:
        return GENERAL_ONSET_QUESTION

    if (
        _has_focal_or_stroke_family_symptom(symptoms)
        and symptoms.laterality.value == "unknown"
        and not _should_skip_laterality_question(symptoms)
    ):
        return "这种症状是只出现在身体一侧，还是两侧都有？"

    if symptoms.progression == Progression.UNKNOWN:
        if symptoms.memory_concern or symptoms.disorientation:
            return CONFUSION_ONSET_QUESTION
        return PROGRESSION_QUESTION

    if symptoms.falls_present and not state.falls_or_injury:
        return "跌倒时有没有撞到头，或者出现明显受伤？"

    return None
