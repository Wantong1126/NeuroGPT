# SPDX-License-Identifier: MIT
"""
NeuroGPT v2 - Question Manager
Decides whether to ask a follow-up question and generates it.
"""

from __future__ import annotations

from core.types import CaseState, ExtractedSymptoms, Onset, Laterality, Progression


SPEECH_ONSET_QUESTION = "这个说话/表达困难是突然出现的吗？大概从什么时候开始？"


def _has_speech_language_symptom(symptoms: ExtractedSymptoms) -> bool:
    return (
        symptoms.red_flags.slurred_speech
        or symptoms.word_finding_difficulty
        or "speech" in symptoms.symptom_type
    )


def _has_non_speech_emergency_feature(symptoms: ExtractedSymptoms) -> bool:
    rf = symptoms.red_flags
    return any(
        [
            rf.weakness_one_side,
            rf.facial_droop,
            rf.seizure,
            rf.loss_of_consciousness,
            rf.head_injury,
            rf.vision_loss and symptoms.onset == Onset.SUDDEN,
            rf.focal_numbness and symptoms.onset == Onset.SUDDEN,
            rf.acute_confusion and symptoms.onset == Onset.SUDDEN,
            rf.severe_headache and symptoms.onset == Onset.SUDDEN,
        ]
    )



def _has_high_risk_red_flags(symptoms: ExtractedSymptoms) -> bool:
    rf = symptoms.red_flags
    has_speech_language_symptom = _has_speech_language_symptom(symptoms)
    return any(
        [
            rf.stroke_beFAST and symptoms.onset == Onset.SUDDEN,
            has_speech_language_symptom and symptoms.onset == Onset.SUDDEN,
            has_speech_language_symptom and _has_non_speech_emergency_feature(symptoms),
            rf.weakness_one_side,
            rf.facial_droop,
            rf.seizure,
            rf.loss_of_consciousness,
            rf.acute_confusion and symptoms.onset == Onset.SUDDEN,
            rf.severe_headache and symptoms.onset == Onset.SUDDEN,
        ]
    )



def decide_question(state: CaseState) -> str | None:
    """Return the single most useful follow-up question, or None."""
    symptoms: ExtractedSymptoms = state.symptoms_detected

    # Do not block obvious emergencies behind more questions.
    if _has_high_risk_red_flags(symptoms):
        return None

    if _has_speech_language_symptom(symptoms):
        if symptoms.onset == Onset.UNKNOWN:
            return SPEECH_ONSET_QUESTION
        return None

    if symptoms.onset == Onset.UNKNOWN:
        return "这个症状是从什么时候开始的？是突然发生的，还是慢慢出现的？"

    if symptoms.laterality == Laterality.UNKNOWN:
        return "这种症状是只出现在身体一侧，还是两侧都有？"

    if symptoms.progression == Progression.UNKNOWN:
        return "最近这个症状有没有加重？比如更频繁，或者更严重？"

    if symptoms.falls_present and not state.falls_or_injury:
        return "跌倒时有没有撞到头，或者出现明显受伤？"

    if symptoms.disorientation or symptoms.memory_concern:
        return "老人家有没有出现突然糊涂、不认人，或者表达明显混乱？"

    return None
