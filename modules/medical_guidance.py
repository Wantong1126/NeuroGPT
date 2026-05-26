# SPDX-License-Identifier: MIT
"""Deterministic source-backed guidance cards.

Guidance explains an action tier that has already been selected elsewhere.
It does not decide risk, diagnosis, care setting, or action level.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from core.config_loader import load_yaml_config
from core.types import ActionLevel, CaseState, Onset


@dataclass(frozen=True)
class GuidanceCard:
    id: str
    title: str
    source_names: tuple[str, ...]
    source_urls: tuple[str, ...]
    applicable_action_levels: tuple[str, ...]
    trigger_red_flags: tuple[str, ...]
    trigger_observation_families: tuple[str, ...]
    snippet_elder: str
    snippet_caregiver: str
    safety_notes: tuple[str, ...]
    forbidden_claims: tuple[str, ...]
    trigger_phrases: tuple[str, ...] = ()


@lru_cache(maxsize=1)
def load_guidance_cards() -> dict[str, GuidanceCard]:
    raw = load_yaml_config("configs/medical_guidance.yaml").get("guidance_cards", {})
    cards: dict[str, GuidanceCard] = {}
    for card_id, data in raw.items():
        cards[card_id] = GuidanceCard(
            id=data.get("id", card_id),
            title=data.get("title", card_id),
            source_names=tuple(data.get("source_names", [])),
            source_urls=tuple(data.get("source_urls", [])),
            applicable_action_levels=tuple(data.get("applicable_action_levels", [])),
            trigger_red_flags=tuple(data.get("trigger_red_flags", [])),
            trigger_observation_families=tuple(data.get("trigger_observation_families", [])),
            snippet_elder=data.get("snippet_elder", ""),
            snippet_caregiver=data.get("snippet_caregiver", ""),
            safety_notes=tuple(data.get("safety_notes", [])),
            forbidden_claims=tuple(data.get("forbidden_claims", [])),
            trigger_phrases=tuple(data.get("trigger_phrases", [])),
        )
    return cards


def select_guidance_cards(state: CaseState, limit: int = 2) -> list[GuidanceCard]:
    """Return at most a couple of conservative guidance cards for this state."""
    cards = load_guidance_cards()
    selected: list[GuidanceCard] = []

    for card_id in (
        "suicidal_language",
        "fall_head_injury",
        "stroke_red_flags",
        "severe_headache",
        "sudden_confusion",
    ):
        card = cards.get(card_id)
        if card and _matches_card(card, state):
            selected.append(card)
        if len(selected) >= limit:
            break

    return selected


def guidance_snippets_for_response(state: CaseState) -> list[str]:
    return [card.snippet_elder for card in select_guidance_cards(state)]


def _matches_card(card: GuidanceCard, state: CaseState) -> bool:
    action = state.action_level.value if state.action_level else ActionLevel.MONITOR.value
    if action not in card.applicable_action_levels:
        return False

    if card.id == "suicidal_language":
        return _has_suicidal_language(state)
    if card.id == "stroke_red_flags":
        return _matches_stroke_like_warning(state, card)
    if card.id == "sudden_confusion":
        return _matches_confusion_warning(state, card)
    if card.id == "severe_headache":
        return _matches_red_flag_or_family(state, card)
    if card.id == "fall_head_injury":
        return _matches_fall_head_injury(state, card)
    return _matches_red_flag_or_family(state, card)


def _matches_red_flag_or_family(state: CaseState, card: GuidanceCard) -> bool:
    return _has_any_red_flag(state, card.trigger_red_flags) or _has_any_family(
        state, card.trigger_observation_families
    )


def _matches_stroke_like_warning(state: CaseState, card: GuidanceCard) -> bool:
    symptoms = state.symptoms_detected
    rf = symptoms.red_flags
    if any([rf.weakness_one_side, rf.facial_droop, rf.slurred_speech, rf.vision_loss]):
        return True
    if symptoms.onset == Onset.SUDDEN and any(
        [
            rf.focal_numbness,
            rf.gait_imbalance,
            _has_any_family(state, card.trigger_observation_families),
        ]
    ):
        return True
    return False


def _matches_confusion_warning(state: CaseState, card: GuidanceCard) -> bool:
    symptoms = state.symptoms_detected
    return (
        _matches_red_flag_or_family(state, card)
        and symptoms.onset in (Onset.SUDDEN, Onset.UNKNOWN)
    )


def _matches_fall_head_injury(state: CaseState, card: GuidanceCard) -> bool:
    symptoms = state.symptoms_detected
    rf = symptoms.red_flags
    if rf.head_injury and any([rf.loss_of_consciousness, rf.seizure, rf.acute_confusion]):
        return True
    return _matches_red_flag_or_family(state, card)


def _has_any_red_flag(state: CaseState, names: tuple[str, ...]) -> bool:
    flags = state.symptoms_detected.red_flags
    return any(bool(getattr(flags, name, False)) for name in names)


def _has_any_family(state: CaseState, families: tuple[str, ...]) -> bool:
    return any(
        observation.symptom_family in families
        for observation in state.symptoms_detected.observations
    )


def _has_suicidal_language(state: CaseState) -> bool:
    card = load_guidance_cards().get("suicidal_language")
    phrases = card.trigger_phrases if card else ()
    haystack = " ".join(
        [
            state.raw_user_input,
            state.symptoms_detected.raw_input,
            *(message.content for message in state.conversation_history if message.role == "user"),
        ]
    ).lower()
    return any(phrase.lower() in haystack for phrase in phrases)
