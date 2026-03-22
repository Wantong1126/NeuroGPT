# SPDX-License-Identifier: MIT
"""
NeuroGPT v2 — Canonical Type Definitions
All structured types, enums, and Pydantic schemas for the pipeline.
Single source of truth — no duplicates across modules.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class ConcernLevel(str, Enum):
    """MVP concern estimation — matches Executive Plan Section 13."""
    HIGH = "high"          # Act now — possible emergency
    MODERATE = "moderate"  # See a doctor soon
    LOW = "low"            # Routine / monitor
    UNCLEAR = "unclear"    # Need more info before deciding


class ActionLevel(str, Enum):
    """Concrete action levels — matches Executive Plan Step 1.4."""
    EMERGENCY_NOW = "emergency_now"        # Call 120/999/911
    SAME_DAY_REVIEW = "same_day_review"   # See doctor today
    PROMPT_FOLLOW_UP = "prompt_follow_up"  # Appointment within 48h–7d
    MONITOR = "monitor"                    # Watch with clear watch-outs
    EDUCATE = "educate"                    # Information only, no urgent action


class RiskLevel(str, Enum):
    """Deterministic safety-engine risk output (internal)."""
    HIGH = "HIGH"       # Call emergency services NOW
    MEDIUM = "MEDIUM"   # See doctor today / within 48h
    LOW = "LOW"         # Routine / monitor
    UNKNOWN = "UNKNOWN" # Insufficient info — ask follow-up


class Onset(str, Enum):
    SUDDEN = "sudden"
    GRADUAL = "gradual"
    CHRONIC = "chronic"
    UNKNOWN = "unknown"


class Laterality(str, Enum):
    ONE_SIDE = "one_side"
    BOTH_SIDES = "both_sides"
    CENTRAL = "central"
    UNKNOWN = "unknown"


class Progression(str, Enum):
    FIRST_TIME = "first_time"
    WORSENING = "worsening"
    STABLE = "stable"
    IMPROVING = "improving"
    RECURRING = "recurring"
    UNKNOWN = "unknown"


# ─────────────────────────────────────────────
# Symptom Extraction
# ─────────────────────────────────────────────

class RedFlags(BaseModel):
    """Clinical red-flag indicators."""
    weakness_one_side: bool = False
    facial_droop: bool = False
    slurred_speech: bool = False
    sudden_onset: bool = False
    acute_confusion: bool = False
    seizure: bool = False
    loss_of_consciousness: bool = False
    severe_headache: bool = False
    vision_loss: bool = False
    gait_imbalance: bool = False
    focal_numbness: bool = False
    new_falls: bool = False
    head_injury: bool = False
    incontinence: bool = False
    stroke_beFAST: bool = False
    seizure_with_postictal: bool = False


class ExtractedSymptoms(BaseModel):
    """Structured symptom profile from Step 2 (symptom_extractor)."""
    raw_input: str = Field(description="Original user input, preserved for audit")
    symptom_type: list[str] = Field(default_factory=list)
    primary_symptom: str = ""
    onset: Onset = Onset.UNKNOWN
    laterality: Laterality = Laterality.UNKNOWN
    duration_text: str = ""
    progression: Progression = Progression.UNKNOWN
    frequency_text: str = ""
    red_flags: RedFlags = Field(default_factory=RedFlags)
    memory_concern: bool = False
    word_finding_difficulty: bool = False
    disorientation: bool = False
    tremor_present: bool = False
    falls_present: bool = False
    gait_difficulty: bool = False
    stiffness: bool = False
    sleep_disturbance: bool = False
    apathy: bool = False
    hallucinations: bool = False
    personality_change: bool = False
    denial_detected: bool = False
    fear_detected: bool = False
    delay_reason: str = ""
    llm_raw_json: str = ""


# ─────────────────────────────────────────────
# Risk & Concern Estimation
# ─────────────────────────────────────────────

class RiskBasis(BaseModel):
    rules_triggered: list[str] = Field(default_factory=list)
    red_flags_count: int = 0
    primary_concern: str = ""


class RiskAssessment(BaseModel):
    """Output of deterministic risk_stratifier (internal use)."""
    risk_level: RiskLevel
    action: ActionLevel
    basis: RiskBasis
    urgency_explanation: str = ""
    key_warning_signs: list[str] = Field(default_factory=list)


class ConcernAssessment(BaseModel):
    """
    Output of concern_estimator — maps RiskAssessment to ConcernLevel
    and adds the explanation component (Executive Plan Section 4.2).
    """
    concern_level: ConcernLevel
    explanation: str = Field(
        description="Plain-language why this symptom pattern deserves attention"
    )
    why_not_normal_ageing: str = Field(
        description="Directly addresses minimization / 'it's just ageing' thinking"
    )
    key_concern_factors: list[str] = Field(default_factory=list)
    risk_assessment: RiskAssessment
    concern_vs_llm_conflict: bool = Field(
        default=False,
        description="True if LLM suggested lower concern than deterministic rules"
    )


# ─────────────────────────────────────────────
# Pipeline State — CaseState
# ─────────────────────────────────────────────

class ConversationMessage(BaseModel):
    role: str = Field(description="'user' or 'assistant'")
    content: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)


class CaseState(BaseModel):
    """
    Canonical state object carried through the entire pipeline.
    Defined by Executive Plan Section 9.
    """
    # Raw input
    raw_user_input: str = ""

    # Extracted symptom fields
    symptoms_detected: ExtractedSymptoms = Field(default_factory=ExtractedSymptoms)

    # Core clinical dimensions (mirrors ExtractedSymptoms for fast access)
    onset: Onset = Onset.UNKNOWN
    duration: str = ""
    progression: Progression = Progression.UNKNOWN
    laterality: Laterality = Laterality.UNKNOWN
    speech_change: bool = False
    consciousness_change: bool = False
    falls_or_injury: bool = False
    cognitive_change: bool = False
    psychological_behavior_flags: bool = False

    # Missing fields
    missing_fields: list[str] = Field(default_factory=list)

    # Hesitation / minimization signals
    hesitation_flags: list[str] = Field(default_factory=list)

    # Pipeline outputs
    concern_level: ConcernLevel = ConcernLevel.UNCLEAR
    action_level: ActionLevel = ActionLevel.MONITOR
    needs_follow_up_question: bool = False
    follow_up_question: Optional[str] = None

    # Response content
    plain_language_rationale: str = ""
    user_message: str = ""
    caregiver_summary: Optional[str] = None

    # Conversation history (lightweight, for multi-turn)
    conversation_history: list[ConversationMessage] = Field(default_factory=list)

    # Meta
    session_id: str = ""
    turn_count: int = 0

    def add_user_message(self, text: str) -> None:
        self.conversation_history.append(
            ConversationMessage(role="user", content=text)
        )
        self.raw_user_input = text
        self.turn_count += 1

    def add_assistant_message(self, text: str) -> None:
        self.conversation_history.append(
            ConversationMessage(role="assistant", content=text)
        )


# ─────────────────────────────────────────────
# Output Contract
# ─────────────────────────────────────────────

class ActionStep(BaseModel):
    step_number: int
    action: str
    reason: str
    what_to_say: str = ""


class ElderResponse(BaseModel):
    """Step 4+5 output — what to tell the elder user."""
    empathy_statement: str = ""
    what_this_means: str = ""
    urgency_statement: str = ""
    action_steps: list[ActionStep] = Field(default_factory=list)
    disclaimer: str = ""
    monitor_points: list[str] = Field(default_factory=list)


class CaregiverSummary(BaseModel):
    """Step 6 output — summary for family caregiver."""
    summary_paragraph: str = ""
    red_flags_summary: list[str] = Field(default_factory=list)
    urgency: str = ""
    recommended_action: str = ""
    what_to_say_to_elder: str = ""
    what_to_say_to_emergency_services: str = ""
    what_to_expect_at_er: str = ""
    questions_for_doctor: list[str] = Field(default_factory=list)


class PipelineOutput(BaseModel):
    """
    Final output contract — matches Executive Plan Section 16.
    Returned by orchestrator to UI.
    """
    needs_follow_up_question: bool
    follow_up_question: Optional[str] = None
    concern_level: str
    action_level: str
    user_message: str
    caregiver_summary: Optional[str] = None
    disclaimer: Optional[str] = None
