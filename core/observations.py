# SPDX-License-Identifier: MIT
"""Structured normalized observations between wording and extraction."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from core.types import Laterality, Onset, Progression


SymptomFamily = Literal[
    "weakness",
    "facial_asymmetry",
    "sensory",
    "speech_language",
    "confusion_awareness",
    "memory_cognitive",
    "gait_balance",
    "headache",
    "vision",
    "seizure_episode",
    "loss_of_consciousness",
    "fall_head_injury",
    "fatigue",
    "other",
]

SignalStrength = Literal["possible", "red_flag_candidate", "true_red_flag"]
DurationCategory = Literal[
    "transient_resolved",
    "minutes_hours",
    "days",
    "weeks_months",
    "years_chronic",
    "unknown",
]
SeverityQualifier = Literal["mild", "moderate", "severe", "unknown"]
ObservationSource = Literal["deterministic", "llm", "merged"]


class NormalizedObservation(BaseModel):
    """A reusable symptom observation with explicit context and strength."""

    raw_text: str = ""
    symptom_family: SymptomFamily = "other"
    signal_strength: SignalStrength = "possible"
    onset: Onset = Onset.UNKNOWN
    duration_text: str = ""
    duration_category: DurationCategory = "unknown"
    laterality: Laterality = Laterality.UNKNOWN
    progression: Progression = Progression.UNKNOWN
    severity_qualifier: SeverityQualifier = "unknown"
    transient_or_resolved: bool = False
    associated_red_flags: list[str] = Field(default_factory=list)
    evidence_text: str = ""
    source: ObservationSource = "deterministic"
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
