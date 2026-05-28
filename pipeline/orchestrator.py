# SPDX-License-Identifier: MIT
"""NeuroGPT v2 - Pipeline Orchestrator."""
from __future__ import annotations

from core.types import ActionStep, CaseState, MVPDebugMetadata, MVPResponsePayload, PipelineOutput
from modules.action_mapper import map_to_action
from modules.concern_estimator import estimate_concern
from modules.hesitation_detector import detect_hesitation
from modules.question_manager import decide_question
from modules.response_builder import build_clarification_response, build_response
from modules.summary_generator import generate_summary
from pipeline.multi_turn import merge_turn
from pipeline.state import new_case


MVP_NEXT_ACTION_LABELS = {
    "emergency_now": "联系当地急救电话或前往急诊",
    "same_day_review": "今天内就医评估",
    "prompt_clinical_review": "尽快预约医生评估",
    "prompt_follow_up": "尽快预约医生",
    "monitor": "继续观察并记录变化",
    "educate": "先了解和观察",
}


def _format_steps(steps: list[ActionStep]) -> str:
    if not steps:
        return ""
    lines = ["【现在怎么做】"]
    for step in steps[:3]:
        lines.append(f"{step.step_number}. {_display_step_action(step.action)}：{_display_step_reason(step.reason)}")
    return "\n".join(lines)



def _format_clarification(question: str | None) -> str:
    if not question:
        return ""
    return f"【接下来要确认】\n{question}"


def _format_caregiver_summary(summary: str) -> str:
    if not summary:
        return ""
    clean_summary = summary.removeprefix("给家属/医生：")
    return f"【给家属/医生的话】\n{clean_summary}"


def _format_guidance(snippets: list[str]) -> str:
    if not snippets:
        return ""
    lines = ["【专业依据提示】"]
    lines.extend(snippets[:1])
    return "\n".join(lines)


def _display_step_action(action: str) -> str:
    replacements = {
        "立即拨打 120/999/911 或直接前往急诊": "联系当地急救电话或前往急诊",
        "立即拨打急救电话或马上去急诊": "联系当地急救电话或前往急诊",
    }
    return replacements.get(action, action)


def _display_step_reason(reason: str) -> str:
    replacements = {
        "当前症状提示可能存在急性神经系统风险。": "需要尽快让医生评估。",
        "当前症状符合高风险神经系统警讯，时间很重要。": "需要尽快让医生评估。",
    }
    return replacements.get(reason, reason)


def _build_assistant_text(
    empathy: str,
    key_signs: str,
    rationale: str,
    guidance_snippets: list[str],
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
            _format_guidance(guidance_snippets),
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
            elder_response.guidance_snippets,
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
            guidance_snippets=elder_response.guidance_snippets,
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
        elder_response.guidance_snippets,
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
        guidance_snippets=elder_response.guidance_snippets,
        disclaimer=elder_response.disclaimer,
    )
    return state, output


def to_mvp_response_payload(state: CaseState, output: PipelineOutput) -> MVPResponsePayload:
    """Serialize existing runtime state into a frontend-ready MVP contract."""
    symptoms = state.symptoms_detected
    return MVPResponsePayload(
        user_message=output.user_message,
        action_level=output.action_level,
        concern_level=output.concern_level,
        next_action_label=MVP_NEXT_ACTION_LABELS.get(output.action_level, output.action_level),
        needs_follow_up_question=output.needs_follow_up_question,
        follow_up_question=_first_display_question(output.follow_up_question),
        caregiver_summary=output.caregiver_summary,
        disclaimer=output.disclaimer,
        guidance_snippets=output.guidance_snippets,
        debug_metadata=MVPDebugMetadata(
            llm_observation_status=symptoms.llm_observation_status.value,
            observation_mode_used=symptoms.observation_mode_used.value,
            llm_observation_error_type=symptoms.llm_observation_error_type,
            deterministic_observation_count=symptoms.deterministic_observation_count,
            llm_observation_count=symptoms.llm_observation_count,
        ),
    )


def _first_display_question(question: str | None) -> str | None:
    if not question:
        return None
    for marker in ("？", "?"):
        index = question.find(marker)
        if index >= 0:
            return question[: index + 1]
    return question
