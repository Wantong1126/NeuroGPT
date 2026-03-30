# SPDX-License-Identifier: MIT
"""Scenario-matrix regression tests for NeuroGPT core logic."""

from __future__ import annotations

import pytest

from core.types import (
    CaseState,
    ExtractedSymptoms,
    Laterality,
    Onset,
    Progression,
    RedFlags,
)
from modules.action_mapper import map_to_action
from modules.concern_estimator import estimate_concern
from modules.hesitation_detector import detect_hesitation

ACTION_PRIORITY = {
    "educate": 0,
    "monitor": 1,
    "prompt_follow_up": 2,
    "same_day_review": 3,
    "emergency_now": 4,
}



def make_symptoms(**kwargs) -> ExtractedSymptoms:
    data = {
        "raw_input": kwargs.pop("raw_input", "scenario input"),
        "onset": Onset.UNKNOWN,
        "laterality": Laterality.UNKNOWN,
        "progression": Progression.UNKNOWN,
        "red_flags": RedFlags(),
    }
    data.update(kwargs)
    return ExtractedSymptoms(**data)


CLINICAL_SCENARIOS = [
    {
        "id": "s001",
        "symptoms": make_symptoms(
            raw_input="sudden one-sided weakness with slurred speech",
            onset=Onset.SUDDEN,
            laterality=Laterality.ONE_SIDE,
            progression=Progression.FIRST_TIME,
            red_flags=RedFlags(weakness_one_side=True, slurred_speech=True, stroke_beFAST=True),
        ),
        "expected_concern": "high",
        "min_action": "emergency_now",
    },
    {
        "id": "s002",
        "symptoms": make_symptoms(
            raw_input="right side cannot move and speech is unclear",
            onset=Onset.SUDDEN,
            laterality=Laterality.ONE_SIDE,
            progression=Progression.FIRST_TIME,
            red_flags=RedFlags(weakness_one_side=True, slurred_speech=True),
        ),
        "expected_concern": "high",
        "min_action": "emergency_now",
    },
    {
        "id": "s003",
        "symptoms": make_symptoms(
            raw_input="sudden severe headache with right-sided numbness",
            onset=Onset.SUDDEN,
            laterality=Laterality.ONE_SIDE,
            progression=Progression.FIRST_TIME,
            red_flags=RedFlags(severe_headache=True, focal_numbness=True),
        ),
        "expected_concern": "high",
        "min_action": "emergency_now",
    },
    {
        "id": "p001",
        "symptoms": make_symptoms(
            raw_input="progressive slowing, shuffling gait, tremor at rest",
            onset=Onset.GRADUAL,
            progression=Progression.WORSENING,
            tremor_present=True,
            gait_difficulty=True,
            stiffness=True,
        ),
        "expected_concern": "moderate",
        "min_action": "prompt_follow_up",
    },
    {
        "id": "p002",
        "symptoms": make_symptoms(
            raw_input="recurrent falls with worsening gait and masked facies",
            onset=Onset.GRADUAL,
            progression=Progression.WORSENING,
            falls_present=True,
            gait_difficulty=True,
        ),
        "expected_concern": "moderate",
        "min_action": "prompt_follow_up",
    },
    {
        "id": "d001",
        "symptoms": make_symptoms(
            raw_input="sudden confusion and does not recognize family",
            onset=Onset.SUDDEN,
            progression=Progression.FIRST_TIME,
            red_flags=RedFlags(acute_confusion=True),
            disorientation=True,
        ),
        "expected_concern": "high",
        "min_action": "emergency_now",
    },
    {
        "id": "d002",
        "symptoms": make_symptoms(
            raw_input="worsening memory decline and disorientation over weeks",
            onset=Onset.GRADUAL,
            progression=Progression.WORSENING,
            memory_concern=True,
            disorientation=True,
        ),
        "expected_concern": "moderate",
        "min_action": "same_day_review",
    },
    {
        "id": "z001",
        "symptoms": make_symptoms(
            raw_input="sudden seizure with loss of consciousness",
            onset=Onset.SUDDEN,
            progression=Progression.FIRST_TIME,
            red_flags=RedFlags(seizure=True, loss_of_consciousness=True),
        ),
        "expected_concern": "high",
        "min_action": "emergency_now",
    },
    {
        "id": "f001",
        "symptoms": make_symptoms(
            raw_input="multiple falls over months with worsening balance",
            onset=Onset.GRADUAL,
            progression=Progression.WORSENING,
            falls_present=True,
            gait_difficulty=True,
        ),
        "expected_concern": "moderate",
        "min_action": "prompt_follow_up",
    },
    {
        "id": "f002",
        "symptoms": make_symptoms(
            raw_input="fall followed by head injury and confusion",
            onset=Onset.SUDDEN,
            progression=Progression.FIRST_TIME,
            red_flags=RedFlags(head_injury=True, acute_confusion=True),
            falls_present=True,
            disorientation=True,
        ),
        "expected_concern": "high",
        "min_action": "emergency_now",
    },
    {
        "id": "y001",
        "symptoms": make_symptoms(
            raw_input="new visual hallucinations with sleep disturbance",
            onset=Onset.GRADUAL,
            progression=Progression.WORSENING,
            hallucinations=True,
            sleep_disturbance=True,
        ),
        "expected_concern": "moderate",
        "min_action": "prompt_follow_up",
    },
    {
        "id": "l001",
        "symptoms": make_symptoms(
            raw_input="chronic mild symptoms that have remained stable",
            onset=Onset.CHRONIC,
            progression=Progression.STABLE,
        ),
        "expected_concern": "low",
        "min_action": "monitor",
    },
]

HESITATION_SCENARIOS = [
    pytest.param("h001", "it is probably just old age", id="h001"),
    pytest.param("h002", "let's wait a few days and see", id="h002"),
    pytest.param("h003", "don't want to worry my family", id="h003"),
]


@pytest.mark.parametrize("scenario", CLINICAL_SCENARIOS, ids=[item["id"] for item in CLINICAL_SCENARIOS])
def test_scenario_matrix_clinical_paths(scenario: dict) -> None:
    state = CaseState(raw_user_input=scenario["symptoms"].raw_input, symptoms_detected=scenario["symptoms"])

    concern = estimate_concern(state)
    action = map_to_action(concern.concern_level)

    assert concern.concern_level.value == scenario["expected_concern"]
    assert ACTION_PRIORITY[action.value] >= ACTION_PRIORITY[scenario["min_action"]]


@pytest.mark.parametrize("scenario_id,text", HESITATION_SCENARIOS)
def test_scenario_matrix_hesitation_detection(scenario_id: str, text: str) -> None:
    state = CaseState(raw_user_input=text)
    flags = detect_hesitation(state)

    assert flags, f"expected hesitation flags for {scenario_id}"
