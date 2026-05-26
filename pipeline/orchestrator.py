# SPDX-License-Identifier: MIT
"""NeuroGPT v2 - Pipeline Orchestrator."""
from __future__ import annotations

from core.types import CaseState, PipelineOutput, ActionStep
from modules.action_mapper import map_to_action
from modules.concern_estimator import estimate_concern
from modules.hesitation_detector import detect_hesitation
from modules.question_manager import decide_question
from modules.response_builder import build_clarification_response, build_response
from modules.summary_generator import generate_summary
from pipeline.multi_turn import merge_turn
from pipeline.state import new_case



def _format_steps(steps: list[ActionStep]) -> str:
    if not steps:
        return ""
    lines = ["【现在怎么做】"]
    for step in steps[:3]:
        lines.append(f"{step.step_number}. {step.action}：{step.reason}")
    return "\n".join(lines)



def _format_clarification(question: str | None) -> str:
    if not question:
        return ""
    return f"【我只需要先确认这一点】\n{question}"


def _format_caregiver_summary(summary: str) -> str:
    if not summary:
        return ""
    return f"【给家属/医生的话】\n{summary}"


def _build_assistant_text(
    empathy: str,
    key_signs: str,
    rationale: str,
    urgency: str,
    steps: list[ActionStep],
    clarification_question: str | None = None,
    caregiver_summary: str = "",
) -> str:
    parts = [
        part.strip()
        for part in (
            empathy,
            key_signs,
            rationale,
            urgency,
            _format_clarification(clarification_question),
            _format_steps(steps),
            _format_caregiver_summary(caregiver_summary),
        )
        if part and part.strip()
    ]
    return "\n\n".join(parts)



def run_pipeline(session_id: str, user_input: str, state: CaseState | None = None):
    """Run the end-to-end pipeline for a single user turn."""
    if state is None:
        state = new_case(session_id=session_id)

    state = merge_turn(state, user_input)
    state.hesitation_flags = detect_hesitation(state)

    question = decide_question(state)
    if question:
        state.needs_follow_up_question = True
        state.follow_up_question = question
        elder_response = build_clarification_response(state, question)
        assistant_text = _build_assistant_text(
            elder_response.empathy_statement,
            elder_response.key_signs_summary,
            elder_response.what_this_means,
            elder_response.urgency_statement,
            elder_response.action_steps,
            elder_response.clarification_question,
            elder_response.caregiver_summary,
        )
        state.user_message = assistant_text
        state.caregiver_summary = elder_response.caregiver_summary
        state.add_assistant_message(assistant_text)
        output = PipelineOutput(
            needs_follow_up_question=True,
            follow_up_question=question,
            concern_level=state.concern_level.value,
            action_level=state.action_level.value,
            user_message=assistant_text,
            caregiver_summary=state.caregiver_summary,
            disclaimer=None,
        )
        return state, output

    state.needs_follow_up_question = False
    state.follow_up_question = None

    concern = estimate_concern(state)
    state.concern_level = concern.concern_level
    state.plain_language_rationale = concern.explanation
    state.why_not_normal_ageing = concern.why_not_normal_ageing
    if concern.concern_level.value == "unclear":
        state.action_level = map_to_action(concern.concern_level)
    else:
        state.action_level = concern.risk_assessment.action

    elder_response = build_response(state)
    assistant_text = _build_assistant_text(
        elder_response.empathy_statement,
        elder_response.key_signs_summary,
        elder_response.what_this_means,
        elder_response.urgency_statement,
        elder_response.action_steps,
        elder_response.clarification_question,
        elder_response.caregiver_summary,
    )
    state.user_message = assistant_text
    state.add_assistant_message(assistant_text)

    caregiver_summary = generate_summary(state)
    state.caregiver_summary = caregiver_summary.summary_paragraph

    output = PipelineOutput(
        needs_follow_up_question=False,
        follow_up_question=None,
        concern_level=state.concern_level.value,
        action_level=state.action_level.value,
        user_message=assistant_text,
        caregiver_summary=caregiver_summary.summary_paragraph,
        disclaimer=elder_response.disclaimer,
    )
    return state, output
