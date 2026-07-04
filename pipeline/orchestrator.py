# SPDX-License-Identifier: MIT
"""NeuroGPT v2 - Pipeline Orchestrator."""
from __future__ import annotations

from core.types import (
    ActionStep,
    CareHomeHandoff,
    CaseState,
    DailyReportItem,
    MVPDebugMetadata,
    MVPResponsePayload,
    PipelineOutput,
)
from modules.action_mapper import map_to_action
from modules.concern_estimator import estimate_concern
from modules.hesitation_detector import detect_hesitation
from modules.observation_extractor_llm import (
    ObservationExtractionResult,
    extract_observation_details,
    format_observation_elder_response,
)
from modules.observation_state_merger import (
    merge_observation_turn,
    plan_next_observation_question,
)
from modules.question_manager import decide_question
from modules.response_builder import (
    ACTION_LABELS,
    FAMILY_LABELS,
    KEY_SIGNS_HEADING,
    build_clarification_response,
    build_key_signs_summary,
    build_response,
)
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

ESCALATION_ACTIONS = {"emergency_now", "same_day_review"}

PSYCHOLOGICAL_MARKERS = (
    "没意思",
    "不想见人",
    "睡不好",
    "睡眠",
    "心情",
    "焦虑",
    "害怕",
    "孤单",
    "不开心",
    "hopeless",
    "withdraw",
    "withdrawn",
    "sleep",
    "appetite",
    "mood",
    "anxiety",
)

NEURO_FAMILIES = {
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
}


def _format_steps(steps: list[ActionStep]) -> str:
    if not steps:
        return ""
    lines = ["【现在怎么做】"]
    for step in steps[:3]:
        lines.append(f"{step.step_number}. {_display_step_action(step.action)}：{_display_step_reason(step.reason)}")
    return "\n".join(lines)



def _format_guidance(snippets: list[str]) -> str:
    if not snippets:
        return ""
    lines = ["为什么要关注"]
    lines.extend(_display_guidance(snippet) for snippet in snippets[:1])
    return "\n".join(lines)


def _display_guidance(snippet: str) -> str:
    replacements = {
        "这些突然出现的神经系统变化属于高风险警讯。现在先不要判断原因，重点是尽快让医生评估。":
            "这些变化是突然出现的，需要尽快让医护人员看一下。",
    }
    return replacements.get(snippet, snippet)


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
        "急诊评估会高度依赖起病时间。": "告诉医护人员什么时候开始不舒服，会帮助他们更快了解情况。",
        "症状需要较快的专业判断。": "需要尽快请医护人员看一下。",
        "症状需要专业评估，但目前未见急救级别红旗。": "需要请医护人员看一下，同时留意有没有加重。",
        "如果出现新红旗或明显加重，需要升级处理。": "如果出现新的不舒服或明显加重，请马上告诉护理员。",
    }
    return replacements.get(reason, reason)


def run_pipeline(session_id: str, user_input: str, state: CaseState | None = None):
    """Run the end-to-end pipeline for a single user turn."""
    if state is None:
        state = new_case(session_id=session_id)

    previous_question = state.pending_question
    previous_pending_field = state.pending_field
    previous_active_observation = state.active_observation.copy()
    state = merge_turn(state, user_input)
    state.hesitation_flags = detect_hesitation(state)

    if previous_active_observation and previous_pending_field:
        merged_observation = merge_observation_turn(
            previous_active_observation,
            user_input,
            previous_question,
            previous_pending_field,
        )
        if merged_observation.pop("topic_changed", False):
            merged_observation.pop("is_answer_to_pending", None)
            state.observation_history.append(merged_observation)
            state.active_observation = {}
            state.pending_question = None
            state.pending_field = None
            state.pending_field_options = []
            state.answered_fields = {}
        elif merged_observation.pop("is_answer_to_pending", False):
            state.active_observation = merged_observation
            state.answered_fields = merged_observation.get("answered_fields", {}).copy()
            _apply_deterministic_assessment(state)
            return _finish_abdominal_observation_turn(state)

    observation_extraction = extract_observation_details(state.raw_user_input)
    _activate_extracted_observation(state, observation_extraction)

    _apply_deterministic_assessment(state)

    if state.active_observation.get("domain") == "abdominal_digestive":
        return _finish_abdominal_observation_turn(state, initial_turn=True)

    deterministic_question = decide_question(state)
    extracted_question = _extracted_next_question(observation_extraction)
    question = None if state.action_level.value == "emergency_now" else (extracted_question or deterministic_question)
    if question:
        state.needs_follow_up_question = True
        state.follow_up_question = question
        elder_response = build_clarification_response(state, question)
        assistant_text = _build_observation_elder_text(
            observation_extraction,
            question,
            state.action_level.value,
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

    elder_response = build_response(state)
    assistant_text = _build_explained_action_text(
        _build_observation_elder_text(
            observation_extraction,
            None,
            state.action_level.value,
        ),
        elder_response.key_signs_summary,
        elder_response.guidance_snippets,
        elder_response.urgency_statement,
        elder_response.action_steps,
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


def _activate_extracted_observation(
    state: CaseState,
    extraction: ObservationExtractionResult,
) -> None:
    if not extraction.observations:
        state.observation_extraction = extraction.model_dump(mode="json")
        return
    active = extraction.observations[0].model_dump(mode="json")
    active["answer_history"] = []
    active["answered_fields"] = {}
    state.active_observation = active
    state.answered_fields = {}
    state.observation_extraction = extraction.model_dump(mode="json")
    state.observation_extraction["observations"] = [*state.observation_history, active]
    state.observation_extraction["active_observation_state"] = active


def _finish_abdominal_observation_turn(
    state: CaseState,
    *,
    initial_turn: bool = False,
) -> tuple[CaseState, PipelineOutput]:
    active = state.active_observation
    question, pending_field, options = plan_next_observation_question(active)
    state.pending_question = question
    state.pending_field = pending_field
    state.pending_field_options = options
    state.needs_follow_up_question = question is not None
    state.follow_up_question = question

    _sync_active_observation_extraction(state)
    caregiver_summary = state.observation_extraction["recommended_staff_handoff"]
    state.caregiver_summary = caregiver_summary

    if question:
        if initial_turn:
            report = active.get("raw_quote", "").strip().rstrip("。.!！")
            if report.startswith("我"):
                report = report[1:].lstrip("，, ")
            assistant_text = f"我听到您说{report}。我先帮您记下来。请您再告诉我：{question}"
        else:
            assistant_text = f"已记录：{_abdominal_known_summary(active)}。请您再告诉我：{question}"
    else:
        assistant_text = "我已经帮您把情况记录下来了，会提醒护理员尽快确认。"

    if state.action_level.value in ESCALATION_ACTIONS:
        urgent_text = "请马上叫护理员过来看一下。"
        if urgent_text not in assistant_text:
            assistant_text = f"{assistant_text}{urgent_text}"

    state.observation_extraction["recommended_elder_response"] = assistant_text
    state.user_message = assistant_text
    state.add_assistant_message(assistant_text)
    return state, PipelineOutput(
        needs_follow_up_question=question is not None,
        follow_up_question=question,
        concern_level=state.concern_level.value,
        action_level=state.action_level.value,
        user_message=assistant_text,
        caregiver_summary=caregiver_summary,
        guidance_snippets=[],
        disclaimer=None,
    )


def _sync_active_observation_extraction(state: CaseState) -> None:
    active = state.active_observation
    active["missing_information"] = _abdominal_missing_information(active)
    active["answer_history"] = active.get("answer_history", [])
    active["answered_fields"] = active.get("answered_fields", {})
    observations = [*state.observation_history, active]
    state.observation_extraction = {
        "observations": observations,
        "active_observation_state": active,
        "overall_plain_summary": _abdominal_known_summary(active),
        "recommended_elder_response": state.user_message,
        "recommended_staff_handoff": _abdominal_staff_handoff(active),
        "recommended_family_summary_after_confirmation": (
            "老人反映腹部不适，护理员将确认具体情况并继续关注。"
        ),
    }


def _abdominal_known_summary(observation: dict) -> str:
    location = observation.get("body_location") or "腹部"
    quality = (observation.get("sensation_quality") or "不舒服").replace("、", "和")
    return f"{location}{quality}"


def _abdominal_missing_information(observation: dict) -> list[str]:
    missing = []
    if not observation.get("body_location"):
        missing.append("腹部具体位置")
    if not observation.get("sensation_quality"):
        missing.append("痛、胀、绞痛、烧心或恶心等感觉")
    if not observation.get("duration"):
        missing.append("持续多久")
    if not observation.get("severity") or not observation.get("progression"):
        missing.append("是否加重及对走路、吃饭或说话的影响")
    if not observation.get("associated_symptoms_checked"):
        missing.append("是否伴随发热、呕吐、腹泻、胸闷气短、黑便或血便等")
    return missing


def _abdominal_staff_handoff(observation: dict) -> str:
    answers = [entry.get("answer", "") for entry in observation.get("answer_history", []) if entry.get("answer")]
    added = "；".join(answers) or "暂无补充"
    missing = "、".join(_abdominal_missing_information(observation)) or "无"
    return (
        f"老人原话：{observation.get('raw_quote', '')}。"
        f"已补充：{added}。仍需确认：{missing}。建议护理员尽快查看老人。"
    )


def _apply_deterministic_assessment(state: CaseState) -> None:
    concern = estimate_concern(state)
    state.concern_level = concern.concern_level
    state.plain_language_rationale = concern.explanation
    state.why_not_normal_ageing = concern.why_not_normal_ageing
    if concern.concern_level.value == "unclear":
        state.action_level = map_to_action(concern.concern_level)
    else:
        state.action_level = concern.risk_assessment.action


def _extracted_next_question(extraction: ObservationExtractionResult) -> str | None:
    for observation in extraction.observations:
        if observation.domain == "general" and observation.confidence == "fallback":
            continue
        if observation.next_best_question.strip():
            return observation.next_best_question.strip()
    return None


def _build_observation_elder_text(
    extraction: ObservationExtractionResult,
    question: str | None,
    action_level: str,
) -> str:
    observation = extraction.observations[0] if extraction.observations else None
    if observation:
        response = format_observation_elder_response(
            observation,
            question,
            include_question=bool(question),
            max_chars=None if action_level in ESCALATION_ACTIONS else 220,
        )
    elif question:
        quote = extraction.overall_plain_summary.rstrip("。.!！")
        response = f"我听到您说{quote}。请您再告诉我：{question}"
    else:
        quote = extraction.overall_plain_summary.rstrip("。.!！")
        response = f"我听到您说{quote}。我已经记录下来了。"

    if action_level in {"emergency_now", "same_day_review"}:
        urgent_text = "请马上叫护理员过来看一下。"
        if urgent_text not in response:
            response = f"{response}{urgent_text}"
    return response


def _build_explained_action_text(
    explanation: str,
    key_signs: str,
    guidance_snippets: list[str],
    urgency: str,
    steps: list[ActionStep],
) -> str:
    parts = [
        explanation,
        key_signs,
        _format_guidance(guidance_snippets),
        urgency,
        _format_steps(steps),
    ]
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


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
        care_home_handoff=build_care_home_handoff(state, output),
        daily_report_item=build_daily_report_item(state, output),
        debug_metadata=MVPDebugMetadata(
            llm_observation_status=symptoms.llm_observation_status.value,
            observation_mode_used=symptoms.observation_mode_used.value,
            llm_observation_error_type=symptoms.llm_observation_error_type,
            deterministic_observation_count=symptoms.deterministic_observation_count,
            llm_observation_count=symptoms.llm_observation_count,
        ),
    )


def build_care_home_handoff(state: CaseState, output: PipelineOutput) -> CareHomeHandoff:
    """Build a deterministic staff handoff from existing pipeline state."""
    action_level = output.action_level
    escalation_needed = _escalation_needed(action_level)
    warning_signs = _red_flag_labels(state)
    known_facts = _known_facts(state)
    missing_info = _missing_critical_info(state, output, escalation_needed)
    follow_up_tasks = _follow_up_tasks(state, escalation_needed)
    caregiver_brief = output.caregiver_summary or state.caregiver_summary or _resident_summary(state)

    return CareHomeHandoff(
        resident_summary=_resident_summary(state),
        known_facts=known_facts,
        missing_critical_info=missing_info,
        risk_status=f"{output.concern_level}/{action_level}",
        escalation_reason="、".join(warning_signs[:4]) if escalation_needed and warning_signs else None,
        recommended_staff_action=_recommended_staff_action(action_level),
        follow_up_tasks=follow_up_tasks,
        suggested_next_observations=_suggested_next_observations(state, escalation_needed),
        caregiver_brief=_clean_summary(caregiver_brief),
    )


def build_daily_report_item(state: CaseState, output: PipelineOutput) -> DailyReportItem:
    """Build one structured care-home daily review event item."""
    handoff = build_care_home_handoff(state, output)
    category = _daily_category(state)
    escalation_needed = _escalation_needed(output.action_level)

    return DailyReportItem(
        headline=_daily_headline(state, output.action_level),
        category=category,
        risk_level=output.concern_level,
        action_level=output.action_level,
        summary_for_department=_summary_for_department(handoff),
        unresolved_questions=handoff.missing_critical_info[:4],
        staff_follow_up_needed=bool(
            output.needs_follow_up_question
            or handoff.follow_up_tasks
            or output.action_level != "educate"
        ),
        escalation_needed=escalation_needed,
    )


def _value(value: object) -> str:
    return str(getattr(value, "value", value) or "")


def _short_text(text: str, limit: int = 80) -> str:
    clean = " ".join((text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "..."


def _clean_summary(summary: str) -> str:
    return (summary or "").removeprefix("给家属/医生：").strip()


def _key_signs_text(state: CaseState) -> str:
    return build_key_signs_summary(state).replace(KEY_SIGNS_HEADING, "").strip()


def _resident_summary(state: CaseState) -> str:
    signs = _key_signs_text(state).rstrip("。")
    raw = _short_text(state.raw_user_input)
    if signs and "目前没有听到" not in signs:
        return f"居民报告：{signs}。"
    if raw:
        return f"居民报告：{raw}。"
    return "居民报告了需要继续了解的身体或情绪变化。"


def _known_facts(state: CaseState) -> list[str]:
    facts: list[str] = []
    signs = _key_signs_text(state).rstrip("。")
    if signs:
        facts.append(f"已知症状：{signs}")

    onset = _value(state.symptoms_detected.onset)
    if onset == "sudden":
        facts.append("发生特点：突然出现")
    elif onset == "chronic":
        facts.append("发生特点：持续较久或逐渐变化")
    elif state.symptoms_detected.duration_text:
        facts.append(f"持续时间：{state.symptoms_detected.duration_text}")

    laterality = _value(state.symptoms_detected.laterality)
    if laterality == "one_side":
        facts.append("部位特点：偏一侧")
    elif laterality == "both_sides":
        facts.append("部位特点：两侧")

    for observation in state.symptoms_detected.observations:
        family = _value(observation.symptom_family)
        if family == "other":
            continue
        label = FAMILY_LABELS.get(family, family)
        if observation.evidence_text:
            fact = f"结构化观察：{label}（{_short_text(observation.evidence_text, 40)}）"
        else:
            fact = f"结构化观察：{label}"
        if fact not in facts:
            facts.append(fact)
        if len(facts) >= 5:
            break

    return facts or ["已知症状：居民报告了不适，但结构化信息仍有限。"]


def _red_flag_labels(state: CaseState) -> list[str]:
    rf = state.symptoms_detected.red_flags
    labels = [
        (rf.weakness_one_side, "单侧无力"),
        (rf.facial_droop, "面部歪斜"),
        (rf.slurred_speech, "说话不清"),
        (rf.sudden_onset, "突然起病"),
        (rf.acute_confusion, "急性意识或认知改变"),
        (rf.seizure, "抽搐"),
        (rf.loss_of_consciousness, "意识丧失"),
        (rf.severe_headache, "剧烈头痛"),
        (rf.vision_loss, "视力突然改变"),
        (rf.gait_imbalance, "走路或平衡明显改变"),
        (rf.focal_numbness, "局灶麻木"),
        (rf.new_falls, "新近跌倒"),
        (rf.head_injury, "头部受伤"),
    ]
    return [label for present, label in labels if present]


def _missing_critical_info(
    state: CaseState,
    output: PipelineOutput,
    escalation_needed: bool,
) -> list[str]:
    items: list[str] = []

    def add(item: str) -> None:
        if item not in items:
            items.append(item)

    if escalation_needed:
        add("准确起病时间")
        add("症状现在是否仍在持续或加重")
        add("是否出现单侧无力、面部歪斜或说话不清")
        add("是否发生跌倒、头部受伤或意识丧失")
    else:
        add("症状是否反复出现")
        add("症状是否正在加重")
        add("是否影响走路、进食、说话或日常活动")
        add("与老人平时状态相比是否不同")

    if _has_psychological_context(state):
        add("近几天情绪、睡眠、食欲和社交变化")

    question = _first_display_question(output.follow_up_question or state.follow_up_question)
    if question:
        add(f"待老人确认：{question}")

    return items


def _follow_up_tasks(state: CaseState, escalation_needed: bool) -> list[str]:
    tasks: list[str] = []

    def add(task: str) -> None:
        if task not in tasks:
            tasks.append(task)

    if escalation_needed:
        add("记录准确起病时间和持续时间")
        add("确认症状是否仍在持续或加重")
        add("检查说话是否清楚")
        add("观察面部是否对称")
        add("检查单侧手臂或腿部力量")
        add("询问是否跌倒、头部受伤或意识丧失")
        add("记录与老人平时基线相比是否明显不同")
    else:
        add("确认症状是否仍在持续")
        add("记录是否反复出现或加重")
        add("观察是否影响走路、进食、说话或日常活动")
        add("留意是否出现新的单侧无力、面部歪斜、说话不清或意识改变")
        add("记录与老人平时基线相比是否不同")

    if _has_psychological_context(state):
        add("询问近几天情绪、睡眠、食欲和社交变化")
        add("安排工作人员复核心理/社交状态并记录变化")

    return tasks


def _suggested_next_observations(state: CaseState, escalation_needed: bool) -> list[str]:
    observations = [
        "症状开始时间和持续时间",
        "与老人平时基线的差异",
    ]
    families = {_value(obs.symptom_family) for obs in state.symptoms_detected.observations}
    if escalation_needed or families & {"weakness", "facial_asymmetry", "speech_language", "sensory"}:
        observations.extend(["语言清晰度", "面部对称性", "单侧肢体力量或麻木"])
    if families & {"gait_balance", "fall_head_injury"} or state.falls_or_injury:
        observations.extend(["步态和平衡", "跌倒或头部受伤线索"])
    if families & {"confusion_awareness", "memory_cognitive"} or state.cognitive_change:
        observations.extend(["意识和定向力", "近期记忆和认知变化"])
    if _has_psychological_context(state):
        observations.extend(["情绪", "睡眠", "食欲", "社交意愿"])
    return _dedupe(observations)[:8]


def _recommended_staff_action(action_level: str) -> str:
    if action_level == "emergency_now":
        return "立即通知值班医护并联系当地急救/急诊流程；不要让老人独自等待。"
    if action_level == "same_day_review":
        return "今天内通知医护人员评估，并记录症状变化。"
    if action_level in {"prompt_clinical_review", "prompt_follow_up"}:
        return "安排医护复核并尽快预约临床评估。"
    if action_level == "monitor":
        return "继续观察并记录变化；如出现红旗信号立即升级。"
    return "记录本次情况，按机构流程继续观察。"


def _daily_category(state: CaseState) -> str:
    families = {_value(obs.symptom_family) for obs in state.symptoms_detected.observations}
    rf = state.symptoms_detected.red_flags
    if "fall_head_injury" in families or rf.head_injury or rf.new_falls or state.falls_or_injury:
        return "fall_or_injury"
    if "memory_cognitive" in families or "confusion_awareness" in families or state.cognitive_change:
        return "cognitive_change"
    if _has_psychological_context(state):
        return "psychological_wellbeing"
    if families & NEURO_FAMILIES or _red_flag_labels(state):
        return "neuro_symptom"
    return "general_monitoring"


def _has_psychological_context(state: CaseState) -> bool:
    raw = (state.raw_user_input or "").lower()
    if state.psychological_behavior_flags or state.symptoms_detected.apathy or state.symptoms_detected.sleep_disturbance:
        return True
    return any(marker in raw for marker in PSYCHOLOGICAL_MARKERS)


def _daily_headline(state: CaseState, action_level: str) -> str:
    action = ACTION_LABELS.get(action_level, action_level)
    signs = _key_signs_text(state).rstrip("。")
    if signs and "目前没有听到" not in signs:
        return f"{action}：{_short_text(signs, 36)}"
    raw = _short_text(state.raw_user_input, 36)
    if raw:
        return f"{action}：{raw}"
    return f"{action}：居民状态变化待复核"


def _summary_for_department(handoff: CareHomeHandoff) -> str:
    known = "；".join(handoff.known_facts[:3])
    action = handoff.recommended_staff_action
    if known and action:
        return f"{known}。建议：{action}"
    return handoff.resident_summary


def _escalation_needed(action_level: str) -> bool:
    return action_level in ESCALATION_ACTIONS


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def _first_display_question(question: str | None) -> str | None:
    if not question:
        return None
    for marker in ("？", "?"):
        index = question.find(marker)
        if index >= 0:
            return question[: index + 1]
    return question
