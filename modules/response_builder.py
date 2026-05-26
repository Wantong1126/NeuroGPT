# SPDX-License-Identifier: MIT
"""NeuroGPT v2 - Response Builder."""
from __future__ import annotations

from core.config_loader import load_yaml_config
from core.observations import NormalizedObservation
from core.types import ActionStep, CaseState, ElderResponse
from modules.medical_guidance import guidance_snippets_for_response

DEFAULT_ACTIONS = {
    "emergency_now": {
        "urgency": "【现在就行动】请立即呼叫急救或立刻去急诊。不要继续观察，不要等。",
        "steps": [
            {"action": "立即拨打急救电话或马上去急诊", "reason": "当前症状符合高风险神经系统警讯，时间很重要。"},
            {"action": "记录症状最早开始的时间", "reason": "医生会根据起病时间决定处理方式。"},
            {"action": "不要自行开车前往", "reason": "症状可能在途中突然加重。"},
        ],
    },
    "same_day_review": {
        "urgency": "【今天内处理】请今天内尽快就医，不要拖到明天以后。",
        "steps": [
            {"action": "今天联系门诊或急诊进行评估", "reason": "症状需要较快的专业判断。"},
            {"action": "整理目前症状和用药清单", "reason": "方便医生快速判断。"},
        ],
    },
    "prompt_follow_up": {
        "urgency": "【尽快安排】请尽快预约医生评估，最好在 48 小时内完成。",
        "steps": [
            {"action": "48 小时内预约就诊", "reason": "症状需要专业评估，但目前未见急救级别红旗。"},
            {"action": "记录症状是否加重", "reason": "便于后续判断病程。"},
        ],
    },
    "monitor": {
        "urgency": "【目前先观察】暂时没有识别到急救级红旗，但如果出现变化或加重，要马上升级处理。",
        "steps": [
            {"action": "继续观察并记录症状变化", "reason": "便于后续就诊时提供病程线索。"},
            {"action": "一旦出现新红旗，立即就医", "reason": "例如突然无力、言语不清、意识改变、抽搐、持续加重。"},
        ],
    },
}

FAMILY_LABELS = {
    "weakness": "无力",
    "facial_asymmetry": "面部歪斜",
    "sensory": "麻木或感觉异常",
    "speech_language": "说话或表达困难",
    "confusion_awareness": "意识或认知改变",
    "memory_cognitive": "记忆或认知问题",
    "gait_balance": "走路或平衡问题",
    "headache": "头痛",
    "vision": "视力变化",
    "seizure_episode": "抽搐",
    "loss_of_consciousness": "意识丧失",
    "fall_head_injury": "跌倒或头部受伤",
    "fatigue": "疲乏",
    "other": "还不明确的不适",
}

LATERALITY_LABELS = {
    "one_side": "偏一侧",
    "both_sides": "两侧",
    "central": "中间部位",
}

ONSET_LABELS = {
    "sudden": "突然出现",
    "gradual": "逐渐出现",
    "chronic": "持续较久",
}

ACTION_LABELS = {
    "emergency_now": "立即急诊/急救",
    "same_day_review": "今天内就医",
    "prompt_clinical_review": "尽快临床评估",
    "prompt_follow_up": "尽快预约医生",
    "monitor": "先观察并留意变化",
    "educate": "先了解和观察",
}



def _load_action_tiers() -> dict:
    try:
        config = load_yaml_config("configs/action_tiers.yaml")
    except Exception:
        return DEFAULT_ACTIONS

    if "action_tiers" in config and isinstance(config["action_tiers"], dict):
        return config["action_tiers"]

    return config if isinstance(config, dict) else DEFAULT_ACTIONS


def _value(value: object) -> str:
    return str(getattr(value, "value", value) or "")


def _observation_phrase(observation: NormalizedObservation) -> str:
    family = FAMILY_LABELS.get(observation.symptom_family, "不适")
    parts: list[str] = []

    laterality = LATERALITY_LABELS.get(_value(observation.laterality))
    onset = ONSET_LABELS.get(_value(observation.onset))
    if laterality:
        parts.append(laterality)
    if observation.signal_strength == "possible":
        parts.append(f"可能有{family}")
    else:
        parts.append(family)
    if onset:
        parts.append(onset)

    return "".join(parts)


def build_key_signs_summary(state: CaseState) -> str:
    """Summarize structured observations in elder-friendly wording."""
    observations = [
        observation
        for observation in state.symptoms_detected.observations
        if observation.symptom_family != "other" or observation.clarification_needed
    ]
    phrases: list[str] = []
    for observation in observations:
        phrase = _observation_phrase(observation)
        if phrase and phrase not in phrases:
            phrases.append(phrase)
        if len(phrases) >= 4:
            break

    if not phrases:
        return "【我目前抓到的重点】目前还没有抓到明确的神经系统红旗信号。"
    return f"【我目前抓到的重点】{'、'.join(phrases)}。"


def build_caregiver_doctor_summary(state: CaseState) -> str:
    signs = build_key_signs_summary(state).replace("【我目前抓到的重点】", "").strip()
    action = ACTION_LABELS.get(state.action_level.value, state.action_level.value)
    timing = ""
    if _value(state.symptoms_detected.onset) == "unknown":
        timing = "起病时间未确认，"
    return f"给家属/医生：{signs}{timing}系统建议：{action}。"


def _first_question(question: str) -> str:
    for marker in ("？", "?"):
        index = question.find(marker)
        if index >= 0:
            return question[: index + 1]
    return question


def _build_empathy(state: CaseState) -> str:
    if state.concern_level.value == "high":
        return "【先说结论】这些情况不能按普通不舒服来看，需要马上处理。"
    if state.concern_level.value == "moderate":
        return "【需要重视】这些情况不是先拖一拖再说，应该尽快让医生评估。"
    if state.concern_level.value == "low":
        return "【暂时不属于急救级】我先把风险说清楚，再告诉你什么时候要立刻升级处理。"
    return "【信息还不够】我先把现在能判断的部分说清楚。"



def _warning_signs(state: CaseState) -> list[str]:
    rf = state.symptoms_detected.red_flags
    signs = []
    if rf.weakness_one_side:
        signs.append("单侧无力")
    if rf.facial_droop:
        signs.append("面部歪斜")
    if rf.slurred_speech:
        signs.append("言语不清")
    if rf.acute_confusion:
        signs.append("急性意识或认知改变")
    if rf.seizure:
        signs.append("抽搐")
    if rf.loss_of_consciousness:
        signs.append("意识丧失")
    if rf.severe_headache:
        signs.append("剧烈头痛")
    if state.symptoms_detected.gait_difficulty:
        signs.append("走路明显变差")
    return signs



def _build_meaning(state: CaseState) -> str:
    warning_signs = _warning_signs(state)
    warning_text = "、".join(warning_signs[:4]) if warning_signs else "目前没有提取到明确的急救级红旗"

    if state.concern_level.value == "high":
        return f"【为什么要马上动】当前信息里已经出现高风险警讯：{warning_text}。这类情况关键不是先想原因，而是先尽快就医。"
    if state.concern_level.value == "moderate":
        return "【为什么不能拖】当前情况值得尽快就医评估。现在最重要的是尽快排除更严重的问题，而不是继续等它自己好。"
    if state.concern_level.value == "low":
        return "【为什么现在先观察】目前没有识别到明确高风险模式。重点不是放松警惕，而是继续观察有没有新变化。"
    return "【为什么还不能下结论】目前信息不足，不能安全地直接判断为没事。"


def build_clarification_response(state: CaseState, question: str) -> ElderResponse:
    """Build a single-question response without changing question selection."""
    return ElderResponse(
        empathy_statement="【我先确认一件关键事】现在还差一个会影响判断的重要信息。",
        key_signs_summary=build_key_signs_summary(state),
        what_this_means="【为什么要问】这个问题能帮助判断是否需要更快就医；在回答前，我不会把它说成诊断。",
        clarification_question=_first_question(question),
        caregiver_summary=build_caregiver_doctor_summary(state),
    )



def build_response(state: CaseState) -> ElderResponse:
    """Build an elder-facing response from populated CaseState."""
    action_tiers = _load_action_tiers()
    disclaimer_cfg = load_yaml_config("configs/disclaimers.yaml")

    tier_key = state.action_level.value if state.action_level else "monitor"
    tier_data = action_tiers.get(tier_key, DEFAULT_ACTIONS["monitor"])

    steps = [
        ActionStep(
            step_number=index,
            action=item.get("action", ""),
            reason=item.get("reason", ""),
            what_to_say=item.get("what_to_say", ""),
        )
        for index, item in enumerate(tier_data.get("steps", []), start=1)
    ]

    empathy = _build_empathy(state)
    key_signs_summary = build_key_signs_summary(state)
    what_this_means = _build_meaning(state)
    guidance_snippets = guidance_snippets_for_response(state)
    disclaimer = disclaimer_cfg.get("disclaimers", {}).get("general", {}).get("short", "")
    caregiver_summary = build_caregiver_doctor_summary(state)

    return ElderResponse(
        empathy_statement=empathy,
        key_signs_summary=key_signs_summary,
        what_this_means=what_this_means,
        guidance_snippets=guidance_snippets,
        urgency_statement=tier_data.get("urgency", DEFAULT_ACTIONS["monitor"]["urgency"]),
        action_steps=steps,
        caregiver_summary=caregiver_summary,
        disclaimer=disclaimer,
        monitor_points=tier_data.get("monitor_points", []),
    )
