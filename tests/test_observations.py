# SPDX-License-Identifier: MIT
"""Tests for structured normalized observations."""

from __future__ import annotations

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
