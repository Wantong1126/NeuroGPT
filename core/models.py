# SPDX-License-Identifier: MIT
"""
NeuroGPT v2 — Core Data Models
Pydantic schemas for all structured data in the pipeline.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────


class RiskLevel(str, Enum):
    HIGH = "HIGH"       # Call emergency services NOW
    MEDIUM = "MEDIUM"   # See doctor today / within 48h
    LOW = "LOW"         # Routine / monitor
    UNKNOWN = "UNKNOWN"  # Insufficient info — ask follow-up


class Onset(str, Enum):
    SUDDEN = "sudden"        # Happened at once (stroke-scale minutes/hours)
    GRADUAL = "gradual"      # Slowly progressed over days/weeks/months
    CHRONIC = "chronic"       # Long-standing, stable for months+
    UNKNOWN = "unknown"


class Laterality(str, Enum):
    ONE_SIDE = "one_side"   # Unilateral — higher concern
    BOTH_SIDES = "both_sides"
    CENTRAL = "central"       # Midline / bilateral symmetric
    UNKNOWN = "unknown"


class Progression(str, Enum):
    FIRST_TIME = "first_time"
    WORSENING = "worsening"
    STABLE = "stable"
    IMPROVING = "improving"
    RECURRING = "recurring"
    UNKNOWN = "unknown"


class ActionTier(str, Enum):
    CALL_AMBULANCE = "call_ambulance"          # 120 / 999 / 911
    GO_TO_ER = "go_to_er"                       # Get to emergency department now
    SEE_DOCTOR_URGENT = "see_doctor_urgent"    # See GP / specialist within 24-48h
    SCHEDULE_ROUTINE = "schedule_routine"         # Non-urgent appointment
    MONITOR = "monitor"                         # Watch and wait with guidance
    EDUCATE = "educate"                         # Provide information, no urgent action


# ─────────────────────────────────────────────
# Symptom Extraction (Step 2 output)
# ─────────────────────────────────────────────

class RedFlags(BaseModel):
    """Clinical red-flag indicators detected in the symptom narrative."""
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
    incontinence: bool = False  # sudden loss of bladder control with neuro symptoms

    # Higher-order computed
    stroke_beFAST: bool = False  # True if face+arm+speech triggered
    seizure_with_postictal: bool = False


class ExtractedSymptoms(BaseModel):
    """
    Structured symptom profile extracted from free-text user input.
    Populated by symptom_extractor (LLM call or stub).
    """
    raw_input: str = Field(description="Original user input, preserved for audit")

    # Core clinical dimensions
    symptom_type: list[str] = Field(
        default_factory=list,
        description="Broad categories: motor, cognitive, speech, behavioral, sensory, autonomic, gait, other"
    )
    primary_symptom: str = Field(description="Single most prominent complaint in user's words")
    onset: Onset = Onset.UNKNOWN
    laterality: Laterality = Laterality.UNKNOWN
    duration_text: str = Field(
        default="",
        description="How long symptoms have been present — as reported by user"
    )
    progression: Progression = Progression.UNKNOWN
    frequency_text: str = Field(
        default="",
        description="Intermittent / constant / single episode"
    )

    # Red flags (deterministic keyword detection)
    red_flags: RedFlags = Field(default_factory=RedFlags)

    # Cognitive
    memory_concern: bool = False
    word_finding_difficulty: bool = False
    disorientation: bool = False

    # Motor
    tremor_present: bool = False
    falls_present: bool = False
    gait_difficulty: bool = False
    stiffness: bool = False

    # Mood / Behavior
    sleep_disturbance: bool = False
    apathy: bool = False
    hallucinations: bool = False
    personality_change: bool = False

    # Persuasion signals (emotional context)
    denial_detected: bool = False
    fear_detected: bool = False
    delay_reason: str = Field(
        default="",
        description="Why the user may be delaying action, if expressed"
    )

    # LLM raw structured output (for audit / trace)
    llm_raw_json: str = Field(
        default="",
        description="Raw JSON string returned by LLM for symptom extraction"
    )


# ─────────────────────────────────────────────
# Risk Stratification (Step 3 output)
# ─────────────────────────────────────────────

class RiskBasis(BaseModel):
    """Why a particular risk level was assigned."""
    rules_triggered: list[str] = Field(
        default_factory=list,
        description="Human-readable list of YAML rule IDs that fired"
    )
    red_flags_count: int = 0
    primary_concern: str = ""


class RiskAssessment(BaseModel):
    """Complete risk stratification output from Step 3."""
    risk_level: RiskLevel
    action: ActionTier
    basis: RiskBasis
    urgency_explanation: str = Field(
        description="Plain-language one-sentence explanation of urgency"
    )
    key_warning_signs: list[str] = Field(
        default_factory=list,
        description="Which specific warning signs drove the risk decision"
    )


# ─────────────────────────────────────────────
# Response Generation (Step 4+5 output)
# ─────────────────────────────────────────────

class ActionStep(BaseModel):
    """A single concrete action item."""
    step_number: int
    action: str           # e.g. "Call 120 / 999 / 911 now"
    reason: str           # Why this step matters
    what_to_say: str = "" # Scripted phrase for user / caregiver


class ElderResponse(BaseModel):
    """
    Output of Step 4+5 — what to tell the elder user.
    """
    empathy_statement: str = Field(
        description="Opening statement that validates the user's experience"
    )
    what_this_means: str = Field(
        description="Plain-language explanation of the symptom significance"
    )
    urgency_statement: str = Field(
        description="Clear statement of how urgent this is"
    )
    action_steps: list[ActionStep] = Field(default_factory=list)
    disclaimer: str = ""  # Auto-injected from configs/disclaimers.yaml
    monitor_points: list[str] = Field(
        default_factory=list,
        description="What to watch for that would change the urgency"
    )


# ─────────────────────────────────────────────
# Caregiver Summary (Step 6 output)
# ─────────────────────────────────────────────

class CaregiverSummary(BaseModel):
    """
    Output of Step 6 — structured summary for family caregiver / adult child.
    """
    summary_paragraph: str = Field(
        description="2-3 sentence plain summary of the situation"
    )
    red_flags_summary: list[str] = Field(
        default_factory=list,
        description="Bullet list of red flags detected"
    )
    urgency: str = Field(description="One sentence on urgency level")
    recommended_action: str = Field(description="Concrete first step for caregiver")
    what_to_say_to_elder: str = Field(
        description="How to persuade the older person to take action"
    )
    what_to_say_to_emergency_services: str = Field(
        description="What to tell the 120/999/911 operator"
    )
    what_to_expect_at_er: str = Field(
        description="Brief description of what may happen at the emergency department"
    )
    questions_for_doctor: list[str] = Field(
        default_factory=list,
        description="Questions to ask the GP or specialist at follow-up"
    )


# ─────────────────────────────────────────────
# Full Pipeline Output
# ─────────────────────────────────────────────

class ConversationTurn(BaseModel):
    """A single exchange in the conversation."""
    user_input: str
    symptoms: ExtractedSymptoms
    risk: RiskAssessment
    elder_response: ElderResponse
    caregiver_summary: CaregiverSummary


class ConversationSession(BaseModel):
    """
    Full session state — carries context across multiple turns.
    """
    session_id: str
    turns: list[ConversationTurn] = Field(default_factory=list)
    memory_summary: str = Field(
        default="",
        description="Rolling summary of conversation so far"
    )

    def latest_turn(self) -> Optional[ConversationTurn]:
        return self.turns[-1] if self.turns else None
