# SPDX-License-Identifier: MIT
"""
NeuroGPT v2 - Step 2: Symptom Extractor.
Uses a provider-selected extractor and deterministic lay-language normalization.
"""
from __future__ import annotations

from core.models import ExtractedSymptoms, Laterality, Onset, Progression, RedFlags
from core.config_loader import load_prompt_template
from core.llm import call_structured
from core.provider_settings import get_provider
from modules.symptom_normalizer import NormalizedSymptomSignals, normalize_symptoms

SYSTEM_PROMPT = (
    "You are a clinical symptom-extraction assistant for a medical education tool "
    "targeting older adults and their caregivers. Your task is to parse free-form "
    "symptom descriptions into a structured clinical profile. "
    "Be conservative: when uncertain, mark fields as unknown rather than guessing."
)

SCHEMA = """
{
  "symptom_type": ["motor", "cognitive", "speech", "behavioral", "sensory", "gait", "other"],
  "primary_symptom": "main complaint in the user's own words",
  "onset": "sudden | gradual | chronic | unknown",
  "laterality": "one_side | both_sides | central | unknown",
  "duration_text": "how long symptoms have been present",
  "progression": "first_time | worsening | stable | improving | recurring | unknown",
  "frequency_text": "intermittent / constant / single episode",
  "red_flags": {
    "weakness_one_side": true,
    "facial_droop": false,
    "slurred_speech": false,
    "sudden_onset": true,
    "acute_confusion": false,
    "seizure": false,
    "loss_of_consciousness": false,
    "severe_headache": false,
    "vision_loss": false,
    "gait_imbalance": false,
    "focal_numbness": false,
    "new_falls": false,
    "head_injury": false,
    "incontinence": false,
    "stroke_beFAST": false
  }
}
"""


def extract_symptoms(user_input: str) -> ExtractedSymptoms:
    """Main entry point."""
    normalized = normalize_symptoms(user_input)
    provider = get_provider("symptom_extractor")
    if provider != "openai_compatible":
        return _from_normalized(user_input, normalized)

    template = load_prompt_template("symptom_extractor") or "Extract clinical features from: {user_input}"
    user_prompt = template.format(user_input=user_input)

    try:
        raw = call_structured(user_prompt, SYSTEM_PROMPT, SCHEMA)
    except Exception:
        return _from_normalized(user_input, normalized)

    return _parse_extracted(raw, user_input, normalized)


def _bool(value) -> bool:
    return bool(value) if value is not None else False


def _enum_or_normalized(value: str, mapping: dict[str, object], normalized_value):
    parsed = mapping.get(value, None)
    if parsed is None or getattr(parsed, "value", None) == "unknown":
        return normalized_value
    return parsed


def _merge_symptom_types(raw_types: list[str], normalized: NormalizedSymptomSignals) -> list[str]:
    merged: list[str] = []
    for symptom_type in [*raw_types, *normalized.symptom_types()]:
        if symptom_type == "speech" and normalized.non_neurological_expression_request:
            continue
        if symptom_type not in merged:
            merged.append(symptom_type)
    return merged or ["other"]


def _build_red_flags(
    rf_data: dict,
    normalized: NormalizedSymptomSignals,
    onset: Onset,
    laterality: Laterality,
) -> RedFlags:
    weakness_one_side = _bool(rf_data.get("weakness_one_side")) or (
        normalized.weakness_possible and laterality == Laterality.ONE_SIDE
    )
    facial_droop = _bool(rf_data.get("facial_droop")) or normalized.facial_asymmetry_possible
    slurred_speech = False if normalized.non_neurological_expression_request else (
        _bool(rf_data.get("slurred_speech")) or normalized.speech_slurring_possible
    )
    word_finding = False if normalized.non_neurological_expression_request else normalized.word_finding_possible
    focal_numbness = _bool(rf_data.get("focal_numbness")) or (
        normalized.sensory_possible and laterality == Laterality.ONE_SIDE
    )

    stroke_befast = _bool(rf_data.get("stroke_beFAST")) or any(
        [
            weakness_one_side,
            facial_droop,
            onset == Onset.SUDDEN and (slurred_speech or word_finding or normalized.speech_language_possible),
            onset == Onset.SUDDEN and normalized.vision_possible,
            onset == Onset.SUDDEN and normalized.gait_balance_possible,
        ]
    )

    return RedFlags(
        weakness_one_side=weakness_one_side,
        facial_droop=facial_droop,
        slurred_speech=slurred_speech,
        sudden_onset=_bool(rf_data.get("sudden_onset")) or onset == Onset.SUDDEN,
        acute_confusion=_bool(rf_data.get("acute_confusion")) or normalized.confusion_awareness_possible,
        seizure=_bool(rf_data.get("seizure")) or normalized.seizure_episode_possible,
        loss_of_consciousness=_bool(rf_data.get("loss_of_consciousness"))
        or normalized.loss_of_consciousness_possible,
        severe_headache=_bool(rf_data.get("severe_headache")) or normalized.headache_possible,
        vision_loss=_bool(rf_data.get("vision_loss")) or normalized.vision_possible,
        gait_imbalance=_bool(rf_data.get("gait_imbalance")) or normalized.gait_balance_possible,
        focal_numbness=focal_numbness,
        new_falls=_bool(rf_data.get("new_falls")) or normalized.fall_possible,
        head_injury=_bool(rf_data.get("head_injury")) or normalized.head_injury_possible,
        incontinence=_bool(rf_data.get("incontinence")) or normalized.incontinence_possible,
        stroke_beFAST=False if normalized.non_neurological_expression_request else stroke_befast,
    )


def _parse_extracted(
    raw: dict,
    user_input: str,
    normalized: NormalizedSymptomSignals,
) -> ExtractedSymptoms:
    """Parse LLM JSON output into Pydantic model and overlay normalized signals."""
    onset_map = {
        "sudden": Onset.SUDDEN,
        "gradual": Onset.GRADUAL,
        "chronic": Onset.CHRONIC,
        "unknown": Onset.UNKNOWN,
    }
    laterality_map = {
        "one_side": Laterality.ONE_SIDE,
        "both_sides": Laterality.BOTH_SIDES,
        "central": Laterality.CENTRAL,
        "unknown": Laterality.UNKNOWN,
    }
    progression_map = {
        "first_time": Progression.FIRST_TIME,
        "worsening": Progression.WORSENING,
        "stable": Progression.STABLE,
        "improving": Progression.IMPROVING,
        "recurring": Progression.RECURRING,
        "unknown": Progression.UNKNOWN,
    }

    onset = _enum_or_normalized(raw.get("onset", "unknown"), onset_map, normalized.onset)
    laterality = _enum_or_normalized(
        raw.get("laterality", "unknown"),
        laterality_map,
        normalized.laterality,
    )
    progression = _enum_or_normalized(
        raw.get("progression", "unknown"),
        progression_map,
        normalized.progression,
    )
    rf_data = raw.get("red_flags", {})
    red_flags = _build_red_flags(rf_data, normalized, onset, laterality)

    return ExtractedSymptoms(
        raw_input=user_input,
        symptom_type=_merge_symptom_types(raw.get("symptom_type", []), normalized),
        primary_symptom=raw.get("primary_symptom", user_input),
        onset=onset,
        laterality=laterality,
        duration_text=raw.get("duration_text", ""),
        progression=progression,
        frequency_text=raw.get("frequency_text", ""),
        red_flags=red_flags,
        memory_concern=_bool(raw.get("memory_concern")) or normalized.memory_cognitive_possible,
        word_finding_difficulty=False
        if normalized.non_neurological_expression_request
        else (_bool(raw.get("word_finding_difficulty")) or normalized.word_finding_possible),
        disorientation=_bool(raw.get("disorientation")) or normalized.confusion_awareness_possible,
        tremor_present=_bool(raw.get("tremor_present")) or normalized.tremor_possible,
        falls_present=_bool(raw.get("falls_present")) or normalized.fall_possible,
        gait_difficulty=_bool(raw.get("gait_difficulty")) or normalized.gait_balance_possible,
        stiffness=_bool(raw.get("stiffness")) or normalized.stiffness_possible,
        sleep_disturbance=_bool(raw.get("sleep_disturbance")),
        apathy=_bool(raw.get("apathy")),
        hallucinations=_bool(raw.get("hallucinations")) or normalized.hallucination_possible,
        personality_change=_bool(raw.get("personality_change"))
        or normalized.personality_change_possible,
        denial_detected=_bool(raw.get("denial_detected")),
        fear_detected=_bool(raw.get("fear_detected")),
        delay_reason=raw.get("delay_reason", ""),
        llm_raw_json=str(raw),
    )


def _from_normalized(user_input: str, normalized: NormalizedSymptomSignals) -> ExtractedSymptoms:
    """Build deterministic extraction output directly from normalized lay-language signals."""
    onset = normalized.onset
    laterality = normalized.laterality
    progression = normalized.progression
    red_flags = _build_red_flags({}, normalized, onset, laterality)

    return ExtractedSymptoms(
        raw_input=user_input,
        symptom_type=_merge_symptom_types([], normalized),
        primary_symptom=user_input[:80],
        onset=onset,
        laterality=laterality,
        progression=progression,
        red_flags=red_flags,
        memory_concern=normalized.memory_cognitive_possible,
        word_finding_difficulty=False
        if normalized.non_neurological_expression_request
        else normalized.word_finding_possible,
        disorientation=normalized.confusion_awareness_possible,
        tremor_present=normalized.tremor_possible,
        falls_present=normalized.fall_possible,
        gait_difficulty=normalized.gait_balance_possible,
        stiffness=normalized.stiffness_possible,
        hallucinations=normalized.hallucination_possible,
        personality_change=normalized.personality_change_possible,
    )
