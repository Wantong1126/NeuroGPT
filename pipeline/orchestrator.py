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

def run_pipeline(session_id: str, user_input: str, state: CaseState | None = None) -> tuple[CaseState, PipelineOutput]:
    """
    Main pipeline entry point.
    1. Accept / update CaseState with new user input.
    2. Run symptom extraction.
    3. Decide whether to ask follow-up question.
    4. If done asking: estimate concern, map to action, build response.
    5. Return (updated_state, PipelineOutput).
    """
    # Initialize or update state
    if state is None:
        from pipeline.state import new_case
        state = new_case(session_id=session_id, user_input=user_input)
    else:
        state.add_user_message(user_input)

    # Step 2: Extract symptoms
    state.symptoms_detected = extract_symptoms(user_input)

    # Step 3: Detect hesitation
    state.hesitation_flags = detect_hesitation(state)

    # Step 4: Decide follow-up question
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

    # Step 5: Estimate concern
    concern = estimate_concern(state)
    state.concern_level = concern.concern_level
    state.plain_language_rationale = concern.explanation

    # Step 6: Map to action
    state.action_level = map_to_action(concern.concern_level)

    # Step 7: Build response
    response = build_response(state)
    state.user_message = response.urgency_statement

    # Step 8: Assemble output
    output = PipelineOutput(
        needs_follow_up_question=False,
        follow_up_question=None,
        concern_level=state.concern_level.value,
        action_level=state.action_level.value,
        user_message=response.model_dump_json(indent=2),
        caregiver_summary=None,
        disclaimer=response.disclaimer,
    )
    return state, output
