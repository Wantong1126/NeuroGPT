# SPDX-License-Identifier: MIT
"""
NeuroGPT v2 - Step 2: Symptom Extractor.
Uses a provider-selected extractor and deterministic lay-language normalization.
"""
from __future__ import annotations

import json
from collections import Counter
from typing import get_args

from core.models import ExtractedSymptoms, Laterality, Onset, Progression, RedFlags
from core.observations import (
    DurationCategory,
    NormalizedObservation,
    ObservationLaterality,
    ObservationOnset,
    ObservationProgression,
    SeverityQualifier,
    SignalStrength,
    SymptomFamily,
)
from core.config_loader import load_prompt_template
from core.llm import call_structured
from core.provider_settings import get_provider
from modules.symptom_normalizer import normalize_observations

SYSTEM_PROMPT = (
    "You extract normalized symptom observations for a medical education tool. "
    "Your job is language understanding only. Do not decide urgency, concern level, "
    "action level, diagnosis, or care setting. When uncertain, use unknown/possible."
)

OBSERVATION_SCHEMA = """
{
  "observations": [
    {
      "raw_text": "original full user text",
      "symptom_family": "weakness | facial_asymmetry | sensory | speech_language | confusion_awareness | memory_cognitive | gait_balance | headache | vision | seizure_episode | loss_of_consciousness | fall_head_injury | fatigue | other",
      "signal_strength": "possible | red_flag_candidate | true_red_flag",
      "onset": "sudden | gradual | chronic | unknown",
      "duration_text": "short phrase describing duration if stated",
      "duration_category": "transient_resolved | minutes_hours | days | weeks_months | years_chronic | unknown",
      "laterality": "one_side | both_sides | central | unknown",
      "progression": "first_time | worsening | stable | improving | recurring | unknown",
      "severity_qualifier": "mild | moderate | severe | unknown",
      "transient_or_resolved": false,
      "associated_red_flags": ["slurred_speech"],
      "evidence_text": "exact user wording supporting this observation",
      "clarification_needed": false,
      "clarification_reason": "short reason when wording is ambiguous",
      "possible_families": ["sensory", "weakness"],
      "confidence": 0.0
    }
  ]
}
"""

OBSERVATION_ENUM_VALUES = {
    "symptom_family": set(get_args(SymptomFamily)),
    "signal_strength": set(get_args(SignalStrength)),
    "onset": set(get_args(ObservationOnset)),
    "duration_category": set(get_args(DurationCategory)),
    "laterality": set(get_args(ObservationLaterality)),
    "progression": set(get_args(ObservationProgression)),
    "severity_qualifier": set(get_args(SeverityQualifier)),
}
OBSERVATION_NULL_DEFAULTS = {
    "duration_text": "",
    "transient_or_resolved": False,
    "associated_red_flags": [],
    "clarification_needed": False,
    "clarification_reason": "",
    "possible_families": [],
}
OBSERVATION_ENUM_ALIASES = {
    "symptom_family": {
        "unknown": "other",
        "unclear": "other",
        "unspecified": "other",
    },
    "duration_category": {
        "seconds": "transient_resolved",
        "resolved": "transient_resolved",
        "transient": "transient_resolved",
        "minutes": "minutes_hours",
        "hours": "minutes_hours",
        "weeks": "weeks_months",
        "months": "weeks_months",
        "several_months": "weeks_months",
        "years": "years_chronic",
    },
    "laterality": {
        "left": "one_side",
        "right": "one_side",
        "left_side": "one_side",
        "right_side": "one_side",
        "unilateral": "one_side",
        "bilateral": "both_sides",
    },
    "progression": {
        "progressive": "worsening",
        "worse": "worsening",
        "recurrent": "recurring",
    },
    "signal_strength": {
        "uncertain": "possible",
        "low": "possible",
    },
}


def extract_symptoms(user_input: str) -> ExtractedSymptoms:
    """Main entry point."""
    deterministic_observations = normalize_observations(user_input)
    provider = get_provider("symptom_extractor")
    if provider != "openai_compatible":
        return _from_observations(user_input, deterministic_observations)

    llm_raw, llm_observations = _extract_llm_observations(user_input)
    merged_observations = merge_observations(deterministic_observations, llm_observations)
    return _from_observations(user_input, merged_observations, llm_raw)


def _bool(value) -> bool:
    return bool(value) if value is not None else False


def _extract_llm_observations(user_input: str) -> tuple[dict, list[NormalizedObservation]]:
    template = load_prompt_template("symptom_observation_extractor") or (
        "Extract normalized symptom observations from this user text. "
        "Return observations only. Do not include action_level, concern_level, diagnosis, "
        "triage advice, or care recommendations.\n\nUser text: {user_input}"
    )
    user_prompt = template.format(user_input=user_input)

    try:
        raw = call_structured(user_prompt, SYSTEM_PROMPT, OBSERVATION_SCHEMA)
    except Exception:
        return {}, []

    return raw, _parse_llm_observations(raw, user_input)


def _parse_llm_observations(raw: object, user_input: str) -> list[NormalizedObservation]:
    observations, _debug = _parse_llm_observations_with_debug(raw, user_input)
    return observations


def _parse_llm_observations_with_debug(
    raw: object,
    user_input: str,
) -> tuple[list[NormalizedObservation], dict]:
    rejection_reasons: Counter[str] = Counter()
    raw_top_level_keys: list[str] = []
    raw_observation_count = 0

    if isinstance(raw, dict):
        raw_top_level_keys = sorted(str(key) for key in raw.keys())
        if "observations" not in raw:
            rejection_reasons["missing_observations_key"] += 1
            return [], _llm_parse_debug(raw_top_level_keys, raw_observation_count, 0, rejection_reasons)
        raw_items = raw.get("observations")
    elif isinstance(raw, list):
        raw_items = raw
    else:
        rejection_reasons["unsupported_shape"] += 1
        return [], _llm_parse_debug(raw_top_level_keys, raw_observation_count, 0, rejection_reasons)

    if not isinstance(raw_items, list):
        rejection_reasons["observations_not_list"] += 1
        return [], _llm_parse_debug(raw_top_level_keys, raw_observation_count, 0, rejection_reasons)

    parsed: list[NormalizedObservation] = []
    raw_observation_count = len(raw_items)
    for item in raw_items:
        if not isinstance(item, dict):
            rejection_reasons["item_not_dict"] += 1
            continue
        data = _normalize_llm_observation_data(item, user_input)
        try:
            observation = NormalizedObservation(**data)
        except Exception as exc:
            rejection_reasons["pydantic_validation_error"] += 1
            for reason in _pydantic_rejection_reasons(exc):
                rejection_reasons[reason] += 1
            continue
        rejection_reason = _llm_observation_rejection_reason(observation)
        if rejection_reason is not None:
            rejection_reasons[rejection_reason] += 1
            continue
        parsed.append(observation)
    return parsed, _llm_parse_debug(raw_top_level_keys, raw_observation_count, len(parsed), rejection_reasons)


def _llm_parse_debug(
    raw_top_level_keys: list[str],
    raw_observation_count: int,
    accepted_observation_count: int,
    rejection_reasons: Counter[str],
) -> dict:
    return {
        "raw_top_level_keys": raw_top_level_keys,
        "raw_observation_count": raw_observation_count,
        "accepted_observation_count": accepted_observation_count,
        "rejection_reasons": dict(sorted(rejection_reasons.items())),
    }


def _normalize_llm_observation_data(item: dict, user_input: str) -> dict:
    """Normalize recoverable LLM shape issues without inferring medical meaning."""
    data = dict(item)
    data["raw_text"] = data.get("raw_text") or user_input
    data["source"] = "llm"

    for field, default in OBSERVATION_NULL_DEFAULTS.items():
        if data.get(field) is None:
            data[field] = list(default) if isinstance(default, list) else default

    if isinstance(data.get("confidence"), str):
        confidence = data["confidence"].strip()
        try:
            data["confidence"] = float(confidence)
        except ValueError:
            pass

    for field in ("associated_red_flags", "possible_families"):
        if data.get(field) is None:
            data[field] = []

    for field in OBSERVATION_ENUM_VALUES:
        if field in data:
            data[field] = _normalize_enum_value(field, data[field])

    if isinstance(data.get("possible_families"), list):
        data["possible_families"] = [
            _normalize_enum_value("symptom_family", value)
            for value in data["possible_families"]
        ]

    return data


def _normalize_enum_value(field: str, value: object) -> object:
    if not isinstance(value, str):
        return value
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    if normalized in OBSERVATION_ENUM_VALUES[field]:
        return normalized
    return OBSERVATION_ENUM_ALIASES.get(field, {}).get(normalized, value)


def _pydantic_rejection_reasons(exc: Exception) -> list[str]:
    errors = getattr(exc, "errors", None)
    if not callable(errors):
        return []
    reasons: list[str] = []
    for error in errors():
        error_type = str(error.get("type", ""))
        if error_type == "literal_error":
            reasons.append("invalid_enum_value")
        elif error_type.endswith("_type") or error_type in {"list_type", "bool_type", "string_type"}:
            reasons.append("unsupported_field_type")
    return sorted(set(reasons))


def _llm_observation_rejection_reason(observation: NormalizedObservation) -> str | None:
    if observation.confidence < 0.5:
        return "low_confidence"
    if not observation.evidence_text.strip():
        return "empty_evidence_text"
    if observation.evidence_text.strip().lower() not in observation.raw_text.lower():
        return "evidence_not_in_raw_text"
    return None


def _valid_llm_observation(observation: NormalizedObservation) -> bool:
    return _llm_observation_rejection_reason(observation) is None


def _strength_rank(strength: str) -> int:
    return {
        "possible": 0,
        "red_flag_candidate": 1,
        "true_red_flag": 2,
    }.get(strength, 0)


def _merge_observation_pair(
    deterministic: NormalizedObservation,
    llm_observation: NormalizedObservation,
) -> NormalizedObservation:
    keep_deterministic_true = deterministic.signal_strength == "true_red_flag"
    signal_strength = deterministic.signal_strength
    if not keep_deterministic_true and _strength_rank(llm_observation.signal_strength) > _strength_rank(signal_strength):
        signal_strength = llm_observation.signal_strength

    onset = deterministic.onset
    if onset == "unknown" and llm_observation.onset != "unknown":
        onset = llm_observation.onset

    laterality = deterministic.laterality
    if laterality == "unknown" and llm_observation.laterality != "unknown":
        laterality = llm_observation.laterality

    progression = deterministic.progression
    if progression == "unknown" and llm_observation.progression != "unknown":
        progression = llm_observation.progression

    duration_category = deterministic.duration_category
    if duration_category == "unknown" and llm_observation.duration_category != "unknown":
        duration_category = llm_observation.duration_category

    duration_text = deterministic.duration_text or llm_observation.duration_text
    severity = deterministic.severity_qualifier
    if severity == "unknown" and llm_observation.severity_qualifier != "unknown":
        severity = llm_observation.severity_qualifier

    associated = list(dict.fromkeys([
        *deterministic.associated_red_flags,
        *llm_observation.associated_red_flags,
    ]))
    possible_families = list(dict.fromkeys([
        *deterministic.possible_families,
        *llm_observation.possible_families,
    ]))
    evidence = "；".join(
        dict.fromkeys(
            item for item in [deterministic.evidence_text, llm_observation.evidence_text] if item
        )
    )

    return deterministic.model_copy(
        update={
            "signal_strength": signal_strength,
            "onset": onset,
            "duration_text": duration_text,
            "duration_category": duration_category,
            "laterality": laterality,
            "progression": progression,
            "severity_qualifier": severity,
            "transient_or_resolved": deterministic.transient_or_resolved
            or llm_observation.transient_or_resolved,
            "associated_red_flags": associated,
            "evidence_text": evidence,
            "clarification_needed": deterministic.clarification_needed
            or llm_observation.clarification_needed,
            "clarification_reason": deterministic.clarification_reason
            or llm_observation.clarification_reason,
            "possible_families": possible_families,
            "source": "merged",
            "confidence": max(deterministic.confidence, llm_observation.confidence),
        }
    )


def merge_observations(
    deterministic_observations: list[NormalizedObservation],
    llm_observations: list[NormalizedObservation],
) -> list[NormalizedObservation]:
    """Merge LLM language observations into deterministic observations conservatively."""
    merged = list(deterministic_observations)

    for llm_observation in llm_observations:
        if not _valid_llm_observation(llm_observation):
            continue

        match_index = next(
            (
                index
                for index, observation in enumerate(merged)
                if observation.symptom_family == llm_observation.symptom_family
            ),
            None,
        )
        if match_index is None:
            merged.append(llm_observation)
            continue

        merged[match_index] = _merge_observation_pair(merged[match_index], llm_observation)

    if any(observation.symptom_family != "other" for observation in merged):
        merged = [observation for observation in merged if observation.symptom_family != "other"]

    return merged


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
            if getattr(value, "value", value) == preferred:
                try:
                    return type(unknown)(preferred)
                except ValueError:
                    continue
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


def _observation_evidence_text(observations: list[NormalizedObservation]) -> str:
    evidence = [obs.evidence_text for obs in observations if obs.evidence_text]
    return "；".join(dict.fromkeys(evidence))


def _observation_audit(raw: dict, observations: list[NormalizedObservation]) -> str:
    payload = {
        "raw": raw,
        "observations": [obs.model_dump(mode="json") for obs in observations],
    }
    return json.dumps(payload, ensure_ascii=False)


def _merge_symptom_types(
    raw_types: list[str],
    observations: list[NormalizedObservation],
) -> list[str]:
    merged: list[str] = []
    for symptom_type in [*raw_types, *_observation_symptom_types(observations)]:
        if symptom_type not in merged:
            merged.append(symptom_type)
    return merged or ["other"]


def _build_red_flags(
    rf_data: dict,
    observations: list[NormalizedObservation],
    onset: Onset,
    laterality: Laterality,
) -> RedFlags:
    weakness_one_side = (
        _bool(rf_data.get("weakness_one_side")) and _has_family(observations, "weakness")
        and not (_has_family(observations, "fatigue") and not _has_family(observations, "weakness"))
    ) or (_has_family(observations, "weakness") and laterality == Laterality.ONE_SIDE)
    facial_droop = (
        _bool(rf_data.get("facial_droop")) and _has_family(observations, "facial_asymmetry")
    ) or _has_family(observations, "facial_asymmetry")
    slurred_speech = (
        _bool(rf_data.get("slurred_speech")) and _has_family(observations, "speech_language")
    ) or _associated(observations, "slurred_speech")
    word_finding = _associated(
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
        incontinence=_bool(rf_data.get("incontinence")),
        stroke_beFAST=stroke_befast,
    )


def _parse_extracted(
    raw: dict,
    user_input: str,
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
    red_flags = _build_red_flags(rf_data, observations, onset, laterality)

    return ExtractedSymptoms(
        raw_input=user_input,
        symptom_type=_merge_symptom_types(raw.get("symptom_type", []), observations),
        primary_symptom=raw.get("primary_symptom", user_input),
        onset=onset,
        laterality=laterality,
        duration_text=raw.get("duration_text", "") or _observation_evidence_text(observations),
        progression=progression,
        frequency_text=raw.get("frequency_text", ""),
        red_flags=red_flags,
        observations=observations,
        weakness_possible=_has_family(observations, "weakness"),
        sensory_possible=_has_family(observations, "sensory"),
        headache_possible=_has_family(observations, "headache"),
        vision_change_possible=_has_family(observations, "vision"),
        transient_or_resolved=_any_transient_or_resolved(observations),
        memory_concern=_bool(raw.get("memory_concern")) or _has_family(observations, "memory_cognitive"),
        word_finding_difficulty=(
            _bool(raw.get("word_finding_difficulty")) and _has_family(observations, "speech_language")
        ) or _associated(observations, "word_finding_difficulty"),
        disorientation=_bool(raw.get("disorientation")) or _has_family(observations, "confusion_awareness"),
        tremor_present=_bool(raw.get("tremor_present")),
        falls_present=_bool(raw.get("falls_present")) or _associated(observations, "fall"),
        gait_difficulty=_bool(raw.get("gait_difficulty")) or _has_family(observations, "gait_balance"),
        stiffness=_bool(raw.get("stiffness")),
        sleep_disturbance=_bool(raw.get("sleep_disturbance")),
        apathy=_bool(raw.get("apathy")),
        hallucinations=_bool(raw.get("hallucinations")),
        personality_change=_bool(raw.get("personality_change")),
        denial_detected=_bool(raw.get("denial_detected")),
        fear_detected=_bool(raw.get("fear_detected")),
        delay_reason=raw.get("delay_reason", ""),
        llm_raw_json=_observation_audit(raw, observations),
    )


def _from_observations(
    user_input: str,
    observations: list[NormalizedObservation],
    raw_debug: dict | None = None,
) -> ExtractedSymptoms:
    """Build deterministic extraction output from structured observations."""
    onset = _aggregate_enum(observations, "onset", Onset.UNKNOWN)
    laterality = _aggregate_enum(observations, "laterality", Laterality.UNKNOWN)
    progression = _aggregate_enum(observations, "progression", Progression.UNKNOWN)
    red_flags = _build_red_flags({}, observations, onset, laterality)

    return ExtractedSymptoms(
        raw_input=user_input,
        symptom_type=_merge_symptom_types([], observations),
        primary_symptom=user_input[:80],
        onset=onset,
        laterality=laterality,
        duration_text=_observation_evidence_text(observations),
        progression=progression,
        red_flags=red_flags,
        observations=observations,
        weakness_possible=_has_family(observations, "weakness"),
        sensory_possible=_has_family(observations, "sensory"),
        headache_possible=_has_family(observations, "headache"),
        vision_change_possible=_has_family(observations, "vision"),
        transient_or_resolved=_any_transient_or_resolved(observations),
        memory_concern=_has_family(observations, "memory_cognitive"),
        word_finding_difficulty=_associated(observations, "word_finding_difficulty"),
        disorientation=_has_family(observations, "confusion_awareness"),
        falls_present=_associated(observations, "fall"),
        gait_difficulty=_has_family(observations, "gait_balance"),
        llm_raw_json=_observation_audit(raw_debug or {}, observations),
    )
