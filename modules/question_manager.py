# SPDX-License-Identifier: MIT
"""
NeuroGPT v2 - Question Manager
Decides whether to ask a follow-up question and generates it.
"""

from __future__ import annotations

from core.types import CaseState, ExtractedSymptoms, Onset, Laterality, Progression



def _has_high_risk_red_flags(symptoms: ExtractedSymptoms) -> bool:
    rf = symptoms.red_flags
    return any(
        [
            rf.stroke_beFAST,
            rf.weakness_one_side,
            rf.facial_droop,
            rf.slurred_speech,
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
