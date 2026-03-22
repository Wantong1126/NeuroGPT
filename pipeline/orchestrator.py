# SPDX-License-Identifier: MIT
"""NeuroGPT v2 — Pipeline Orchestrator. Commands all modules in order."""
from __future__ import annotations
from core.types import CaseState, PipelineOutput
from modules.symptom_extractor import extract_symptoms
from modules.question_manager import decide_question
from modules.concern_estimator import estimate_concern
from modules.action_mapper import map_to_action
from modules.hesitation_detector import detect_hesitation
from modules.response_builder import build_response
from modules.summary_generator import generate_summary


def run_pipeline(session_id: str, user_input: str, state: CaseState | None = None):
    """
    Main pipeline entry point.

    Step 1:  Initialise or update CaseState with new user input.
    Step 2:  Extract structured symptoms from free text.
    Step 3:  Detect hesitation / minimization signals.
    Step 4:  Decide whether a follow-up question is needed.
               If yes → return question immediately (pursue clarification).
    Step 5:  Estimate concern level via deterministic + LLM hybrid.
    Step 6:  Map concern level to action level.
    Step 7:  Build elder-facing response (with hesitation handling).
    Step 8:  Generate caregiver summary.
    Step 9:  Return PipelineOutput to UI.
    """
    # ── Step 1: Init / update state ──────────────────────────────────────────
    if state is None:
        from pipeline.state import new_case
        state = new_case(session_id=session_id, user_input=user_input)
    else:
        state.add_user_message(user_input)

    # ── Step 2: Extract symptoms ─────────────────────────────────────────────
    state.symptoms_detected = extract_symptoms(user_input)

    # ── Step 3: Detect hesitation signals ───────────────────────────────────
    state.hesitation_flags = detect_hesitation(state)

    # ── Step 4: Follow-up question decision ─────────────────────────────────
    question = decide_question(state)
    if question:
        state.needs_follow_up_question = True
        state.follow_up_question = question
        state.add_assistant_message(question)
        output = PipelineOutput(
            needs_follow_up_question=True,
            follow_up_question=question,
            concern_level=state.concern_level.value,
            action_level=state.action_level.value,
            user_message=question,
            caregiver_summary=None,
            disclaimer=None,
        )
        return state, output

    # ── Step 5: Estimate concern ───────────────────────────────────────────────
    concern = estimate_concern(state)
    state.concern_level = concern.concern_level
    state.plain_language_rationale = concern.explanation
    state.why_not_normal_ageing = concern.why_not_normal_ageing

    # ── Step 6: Map to action level ──────────────────────────────────────────
    state.action_level = map_to_action(concern.concern_level)

    # ── Step 7: Build elder-facing response ──────────────────────────────────
    elder_response = build_response(state)
    state.user_message = elder_response.urgency_statement

    # ── Step 8: Generate caregiver summary ──────────────────────────────────
    caregiver_summary_str = None
    try:
        caregiver_sm = generate_summary(state)
        caregiver_summary_str = caregiver_sm.summary_paragraph
    except Exception:
        # summary_generator is a stub until API key is available
        caregiver_summary_str = None

    # ── Step 9: Assemble PipelineOutput ─────────────────────────────────────────
    output = PipelineOutput(
        needs_follow_up_question=False,
        follow_up_question=None,
        concern_level=state.concern_level.value,
        action_level=state.action_level.value,
        user_message=elder_response.model_dump_json(indent=2),
        caregiver_summary=caregiver_summary_str,
        disclaimer=elder_response.disclaimer,
    )
    return state, output
