# SPDX-License-Identifier: MIT
"""
NeuroGPT v2 - Step 2: Symptom Extractor.
Uses a provider-selected extractor and deterministic lay-language normalization.
"""
from __future__ import annotations

from core.models import ExtractedSymptoms, Laterality, Onset, Progression, RedFlags
from core.observations import NormalizedObservation
from core.config_loader import load_prompt_template
from core.llm import call_structured
from core.provider_settings import get_provider
from modules.symptom_normalizer import (
    NormalizedSymptomSignals,
    normalize_symptoms,
    observations_from_signals,
)

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
    observations = observations_from_signals(normalized)
    provider = get_provider("symptom_extractor")
    if provider != "openai_compatible":
        return _from_observations(user_input, normalized, observations)

    template = load_prompt_template("symptom_extractor") or "Extract clinical features from: {user_input}"
    user_prompt = template.format(user_input=user_input)

    try:
        raw = call_structured(user_prompt, SYSTEM_PROMPT, SCHEMA)
    except Exception:
        return _from_observations(user_input, normalized, observations)

    return _parse_extracted(raw, user_input, normalized, observations)


def _bool(value) -> bool:
    return bool(value) if value is not None else False


def _raw_flag_unless_possible_only(raw_value, possible_signal: bool, true_red_flag: bool) -> bool:
    if true_red_flag:
        return True
    if possible_signal:
        return False
    return _bool(raw_value)


def _enum_or_normalized(value: str, mapping: dict[str, object], normalized_value):
    parsed = mapping.get(value, None)
    if parsed is None or getattr(parsed, "value", None) == "unknown":
        return normalized_value
    return parsed


def _has_family(observations: list[NormalizedObservation], family: str) -> bool:
    return any(obs.symptom_family == family for obs in observations)


def _has_true_family(observations: list[NormalizedObservation], family: str) -> bool:
    return any(
        obs.symptom_family == family and obs.signal_strength == "true_red_flag"
        for obs in observations
    )


def _associated(observations: list[NormalizedObservation], flag: str) -> bool:
    return any(flag in obs.associated_red_flags for obs in observations)


def _any_transient_or_resolved(observations: list[NormalizedObservation]) -> bool:
    return any(obs.transient_or_resolved for obs in observations)


def _aggregate_enum(observations: list[NormalizedObservation], attr: str, unknown):
    preferred_values = [
        "sudden",
        "chronic",
        "gradual",
        "one_side",
        "both_sides",
        "central",
        "improving",
        "stable",
        "worsening",
        "first_time",
    ]
    for preferred in preferred_values:
        for obs in observations:
            value = getattr(obs, attr)
            if getattr(value, "value", None) == preferred:
                return value
    return unknown


def _observation_symptom_types(observations: list[NormalizedObservation]) -> list[str]:
    mapped: list[str] = []
    family_to_type = {
        "weakness": "motor",
        "facial_asymmetry": "motor",
        "speech_language": "speech",
        "sensory": "sensory",
        "vision": "sensory",
        "gait_balance": "gait",
        "confusion_awareness": "cognitive",
        "memory_cognitive": "cognitive",
    }
    for obs in observations:
        symptom_type = family_to_type.get(obs.symptom_family, "other")
        if symptom_type not in mapped:
            mapped.append(symptom_type)
    return mapped or ["other"]


def _merge_symptom_types(
    raw_types: list[str],
    observations: list[NormalizedObservation],
    normalized: NormalizedSymptomSignals,
) -> list[str]:
    merged: list[str] = []
    for symptom_type in [*raw_types, *_observation_symptom_types(observations)]:
        if symptom_type == "speech" and normalized.non_neurological_expression_request:
            continue
        if symptom_type not in merged:
            merged.append(symptom_type)
    return merged or ["other"]


def _build_red_flags(
    rf_data: dict,
    observations: list[NormalizedObservation],
    normalized: NormalizedSymptomSignals,
    onset: Onset,
    laterality: Laterality,
) -> RedFlags:
    weakness_one_side = (
        _bool(rf_data.get("weakness_one_side"))
        and not (_has_family(observations, "fatigue") and not _has_family(observations, "weakness"))
    ) or (_has_family(observations, "weakness") and laterality == Laterality.ONE_SIDE)
    facial_droop = _bool(rf_data.get("facial_droop")) or _has_family(observations, "facial_asymmetry")
    slurred_speech = False if normalized.non_neurological_expression_request else (
        _bool(rf_data.get("slurred_speech")) or _associated(observations, "slurred_speech")
    )
    word_finding = False if normalized.non_neurological_expression_request else _associated(
        observations,
        "word_finding_difficulty",
    )
    focal_numbness = (
        _bool(rf_data.get("focal_numbness"))
        and not (_has_family(observations, "sensory") and laterality != Laterality.ONE_SIDE)
    ) or (_has_family(observations, "sensory") and laterality == Laterality.ONE_SIDE)
    vision_loss = _raw_flag_unless_possible_only(
        rf_data.get("vision_loss"),
        _has_family(observations, "vision"),
        _has_true_family(observations, "vision"),
    )
    headache_with_neuro_red_flags = _has_family(observations, "headache") and any(
        [
            weakness_one_side,
            facial_droop,
            slurred_speech,
            word_finding,
            focal_numbness,
            vision_loss,
            _has_family(observations, "confusion_awareness"),
        ]
    )
    severe_headache = _raw_flag_unless_possible_only(
        rf_data.get("severe_headache"),
        _has_family(observations, "headache"),
        _has_true_family(observations, "headache") or headache_with_neuro_red_flags,
    )

    stroke_befast = _bool(rf_data.get("stroke_beFAST")) or any(
        [
            weakness_one_side,
            facial_droop,
            onset == Onset.SUDDEN
            and (slurred_speech or word_finding or _has_family(observations, "speech_language")),
            onset == Onset.SUDDEN and vision_loss,
            onset == Onset.SUDDEN and _has_family(observations, "gait_balance"),
        ]
    )

    return RedFlags(
        weakness_one_side=weakness_one_side,
        facial_droop=facial_droop,
        slurred_speech=slurred_speech,
        sudden_onset=_bool(rf_data.get("sudden_onset")) or onset == Onset.SUDDEN,
        acute_confusion=_bool(rf_data.get("acute_confusion")) or _has_family(observations, "confusion_awareness"),
        seizure=_bool(rf_data.get("seizure")) or _has_family(observations, "seizure_episode"),
        loss_of_consciousness=_bool(rf_data.get("loss_of_consciousness"))
        or _has_family(observations, "loss_of_consciousness"),
        severe_headache=severe_headache,
        vision_loss=vision_loss,
        gait_imbalance=_bool(rf_data.get("gait_imbalance")) or _has_family(observations, "gait_balance"),
        focal_numbness=focal_numbness,
        new_falls=_bool(rf_data.get("new_falls")) or _associated(observations, "fall"),
        head_injury=_bool(rf_data.get("head_injury")) or _associated(observations, "head_injury"),
        incontinence=_bool(rf_data.get("incontinence")) or normalized.incontinence_possible,
        stroke_beFAST=False if normalized.non_neurological_expression_request else stroke_befast,
    )


def _parse_extracted(
    raw: dict,
    user_input: str,
    normalized: NormalizedSymptomSignals,
    observations: list[NormalizedObservation],
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

    observation_onset = _aggregate_enum(observations, "onset", Onset.UNKNOWN)
    observation_laterality = _aggregate_enum(observations, "laterality", Laterality.UNKNOWN)
    observation_progression = _aggregate_enum(observations, "progression", Progression.UNKNOWN)
    onset = _enum_or_normalized(raw.get("onset", "unknown"), onset_map, observation_onset)
    laterality = _enum_or_normalized(
        raw.get("laterality", "unknown"),
        laterality_map,
        observation_laterality,
    )
    progression = _enum_or_normalized(
        raw.get("progression", "unknown"),
        progression_map,
        observation_progression,
    )
    rf_data = raw.get("red_flags", {})
    red_flags = _build_red_flags(rf_data, observations, normalized, onset, laterality)

    return ExtractedSymptoms(
        raw_input=user_input,
        symptom_type=_merge_symptom_types(raw.get("symptom_type", []), observations, normalized),
        primary_symptom=raw.get("primary_symptom", user_input),
        onset=onset,
        laterality=laterality,
        duration_text=raw.get("duration_text", ""),
        progression=progression,
        frequency_text=raw.get("frequency_text", ""),
        red_flags=red_flags,
        weakness_possible=_has_family(observations, "weakness"),
        sensory_possible=_has_family(observations, "sensory"),
        headache_possible=_has_family(observations, "headache"),
        vision_change_possible=_has_family(observations, "vision"),
        transient_or_resolved=_any_transient_or_resolved(observations),
        memory_concern=_bool(raw.get("memory_concern")) or _has_family(observations, "memory_cognitive"),
        word_finding_difficulty=False
        if normalized.non_neurological_expression_request
        else (_bool(raw.get("word_finding_difficulty")) or _associated(observations, "word_finding_difficulty")),
        disorientation=_bool(raw.get("disorientation")) or _has_family(observations, "confusion_awareness"),
        tremor_present=_bool(raw.get("tremor_present")) or normalized.tremor_possible,
        falls_present=_bool(raw.get("falls_present")) or _associated(observations, "fall"),
        gait_difficulty=_bool(raw.get("gait_difficulty")) or _has_family(observations, "gait_balance"),
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


def _from_observations(
    user_input: str,
    normalized: NormalizedSymptomSignals,
    observations: list[NormalizedObservation],
) -> ExtractedSymptoms:
    """Build deterministic extraction output from structured observations."""
    onset = _aggregate_enum(observations, "onset", Onset.UNKNOWN)
    laterality = _aggregate_enum(observations, "laterality", Laterality.UNKNOWN)
    progression = _aggregate_enum(observations, "progression", Progression.UNKNOWN)
    red_flags = _build_red_flags({}, observations, normalized, onset, laterality)

    return ExtractedSymptoms(
        raw_input=user_input,
        symptom_type=_merge_symptom_types([], observations, normalized),
        primary_symptom=user_input[:80],
        onset=onset,
        laterality=laterality,
        progression=progression,
        red_flags=red_flags,
        weakness_possible=_has_family(observations, "weakness"),
        sensory_possible=_has_family(observations, "sensory"),
        headache_possible=_has_family(observations, "headache"),
        vision_change_possible=_has_family(observations, "vision"),
        transient_or_resolved=_any_transient_or_resolved(observations),
        memory_concern=_has_family(observations, "memory_cognitive"),
        word_finding_difficulty=False
        if normalized.non_neurological_expression_request
        else _associated(observations, "word_finding_difficulty"),
        disorientation=_has_family(observations, "confusion_awareness"),
        tremor_present=normalized.tremor_possible,
        falls_present=_associated(observations, "fall"),
        gait_difficulty=_has_family(observations, "gait_balance"),
        stiffness=normalized.stiffness_possible,
        hallucinations=normalized.hallucination_possible,
        personality_change=normalized.personality_change_possible,
    )
