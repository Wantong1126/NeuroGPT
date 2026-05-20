# SPDX-License-Identifier: MIT
"""Tests for structured normalized observations."""

from __future__ import annotations

from core.observations import NormalizedObservation
from modules import symptom_extractor
from modules.symptom_extractor import extract_symptoms
from modules.symptom_normalizer import normalize_observations
from pipeline.orchestrator import run_pipeline


def _observation(text: str, family: str):
    observations = normalize_observations(text)
    return next(obs for obs in observations if obs.symptom_family == family)


def _run_text(text: str):
    return run_pipeline(f"observations-{abs(hash(text))}", text)


def test_mild_headache_observation_stays_non_emergency() -> None:
    obs = _observation("今天有点头痛", "headache")
    _state, output = _run_text("今天有点头痛")

    assert obs.signal_strength == "possible"
    assert obs.severity_qualifier in {"mild", "unknown"}
    assert output.action_level != "emergency_now"


def test_explosive_headache_with_speech_observation_is_emergency() -> None:
    obs = _observation("突然爆炸样头痛，说话不清", "headache")
    _state, output = _run_text("突然爆炸样头痛，说话不清")

    assert obs.signal_strength in {"red_flag_candidate", "true_red_flag"}
    assert "speech_language" in obs.associated_red_flags
    assert output.action_level == "emergency_now"


def test_blurry_vision_observation_stays_non_emergency() -> None:
    obs = _observation("看不清", "vision")
    _state, output = _run_text("看不清")

    assert obs.signal_strength == "possible"
    assert output.action_level != "emergency_now"


def test_sudden_vision_loss_observation_is_emergency() -> None:
    obs = _observation("突然看不见", "vision")
    _state, output = _run_text("突然看不见")

    assert obs.signal_strength == "true_red_flag"
    assert output.action_level == "emergency_now"


def test_transient_hand_numbness_observation_stays_non_emergency() -> None:
    obs = _observation("刚才手麻了一下，现在好了", "sensory")
    _state, output = _run_text("刚才手麻了一下，现在好了")

    assert obs.duration_category == "transient_resolved"
    assert obs.transient_or_resolved is True
    assert output.action_level != "emergency_now"


def test_sudden_one_sided_numbness_with_speech_observations_are_emergency() -> None:
    sensory = _observation("突然半边身子麻，说话不清", "sensory")
    speech = _observation("突然半边身子麻，说话不清", "speech_language")
    _state, output = _run_text("突然半边身子麻，说话不清")

    assert sensory.onset.value == "sudden"
    assert sensory.laterality.value == "one_side"
    assert sensory.signal_strength == "true_red_flag"
    assert speech.signal_strength == "red_flag_candidate"
    assert output.action_level == "emergency_now"


def test_fatigue_observation_stays_non_emergency() -> None:
    obs = _observation("今天有点累，没什么别的症状", "fatigue")
    _state, output = _run_text("今天有点累，没什么别的症状")

    assert obs.signal_strength == "possible"
    assert output.action_level != "emergency_now"


def test_extract_symptoms_deterministic_path_uses_observations(monkeypatch) -> None:
    observation = NormalizedObservation(
        raw_text="synthetic observation only",
        symptom_family="vision",
        signal_strength="true_red_flag",
        evidence_text="synthetic vision loss",
    )
    monkeypatch.setattr(symptom_extractor, "normalize_observations", lambda _text: [observation])

    symptoms = extract_symptoms("plain text without known phrases")

    assert symptoms.vision_change_possible is True
    assert symptoms.red_flags.vision_loss is True
    assert "synthetic vision loss" in symptoms.duration_text
    assert "observations" in symptoms.llm_raw_json


def test_mixed_transient_sensory_and_gait_observations_stay_separate() -> None:
    text = "刚才右手麻了一下，现在好了，但最近走路不稳"
    observations = normalize_observations(text)
    sensory = next(obs for obs in observations if obs.symptom_family == "sensory")
    gait = next(obs for obs in observations if obs.symptom_family == "gait_balance")
    symptoms = extract_symptoms(text)
    _state, output = _run_text(text)

    assert sensory.duration_category == "transient_resolved"
    assert sensory.transient_or_resolved is True
    assert gait.transient_or_resolved is False
    assert gait.duration_category != "transient_resolved"
    assert symptoms.sensory_possible is True
    assert symptoms.gait_difficulty is True
    assert output.action_level != "emergency_now"
