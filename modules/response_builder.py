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

KEY_SIGNS_HEADING = "【我目前抓到的重点】"



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
    raw_phrases = _raw_key_phrases(state.raw_user_input)
    observations = [
        observation
        for observation in state.symptoms_detected.observations
        if observation.symptom_family != "other" or (observation.clarification_needed and not raw_phrases)
    ]
    phrases: list[str] = []
    for observation in observations:
        phrase = _observation_phrase(observation)
        if phrase and phrase not in phrases:
            phrases.append(phrase)
        if len(phrases) >= 4:
            break

    for phrase in raw_phrases:
        if phrase and phrase not in phrases:
            phrases.append(phrase)
        if len(phrases) >= 5:
            break

    if not phrases:
        return f"{KEY_SIGNS_HEADING}目前没有听到明确的急救级红旗信号。"
    return f"{KEY_SIGNS_HEADING}{'、'.join(phrases)}。"


def _raw_key_phrases(text: str) -> list[str]:
    """Add plain-language details only when they are directly present."""
    source = text or ""
    phrase_checks = [
        (("眼前发黑",), "眼前发黑"),
        (("头晕", "眩晕"), "头晕"),
        (("头感觉很重", "头很重", "头重"), "头部沉重"),
        (("起床坐起身", "坐起身", "起身"), "起身或坐起后出现"),
        (("缓了好久才恢复", "缓了好久", "才恢复"), "过一段时间才缓解"),
    ]
    phrases: list[str] = []
    for needles, phrase in phrase_checks:
        if any(needle in source for needle in needles) and phrase not in phrases:
            phrases.append(phrase)
    return phrases


def build_caregiver_doctor_summary(state: CaseState) -> str:
    signs = build_key_signs_summary(state).replace(KEY_SIGNS_HEADING, "").strip()
    action = ACTION_LABELS.get(state.action_level.value, state.action_level.value)
    occurrence = _caregiver_occurrence_text(state)
    rationale = _caregiver_rationale_text(state)
    pieces = [
        f"已知情况：老人{signs}",
        occurrence,
        rationale,
        f"建议：{action}。",
    ]
    return "给家属/医生：" + "".join(piece for piece in pieces if piece)


def _caregiver_occurrence_text(state: CaseState) -> str:
    symptoms = state.symptoms_detected
    onset = _value(symptoms.onset)
    raw_occurrence = _raw_occurrence_text(state.raw_user_input)
    if raw_occurrence:
        return f"发生情况：{raw_occurrence}。"
    if onset == "sudden":
        return "发生情况：起病较突然。"
    if onset == "chronic":
        return "发生情况：病程较久。"
    if _looks_like_time_reference(symptoms.duration_text):
        return f"发生情况：{symptoms.duration_text}。"
    return "还需要确认：起病时间。"


def _raw_occurrence_text(text: str) -> str:
    source = text or ""
    parts: list[str] = []
    if "今天早上" in source:
        parts.append("今天早上")
    elif "早上" in source:
        parts.append("早上")
    elif "today" in source.lower():
        parts.append("today")
    elif "morning" in source.lower():
        parts.append("morning")

    if any(token in source for token in ("起床坐起身", "坐起身", "起身")):
        parts.append("起身或坐起后")

    if any(token in source for token in ("缓了好久才恢复", "缓了好久", "才恢复")):
        parts.append("过一段时间才缓解")

    if not parts and _looks_like_time_reference(source):
        if "over months" in source.lower():
            return "数月来逐渐变化"
        if "months" in source.lower():
            return "持续数月"
        if len(source) <= 40:
            return source

    return "，".join(parts)


def _looks_like_time_reference(text: str) -> bool:
    lowered = (text or "").lower()
    timing_markers = (
        "today",
        "yesterday",
        "morning",
        "hour",
        "day",
        "week",
        "month",
        "year",
        "今天",
        "昨天",
        "早上",
        "小时",
        "天",
        "周",
        "月",
        "年",
    )
    return any(marker in lowered for marker in timing_markers)


def _caregiver_rationale_text(state: CaseState) -> str:
    warning_signs = _warning_signs(state)
    if warning_signs:
        return f"需要升级的理由：{'、'.join(warning_signs[:3])}。"
    if state.concern_level.value == "low":
        return "目前未见明确急救级红旗。"
    if state.concern_level.value == "moderate":
        return "需要尽快排除更严重问题。"
    return ""


def _first_question(question: str) -> str:
    for marker in ("？", "?"):
        index = question.find(marker)
        if index >= 0:
            return question[: index + 1]
    return question


def _build_empathy(state: CaseState) -> str:
    if state.concern_level.value == "high":
        return "【先说结论】这些变化需要现在处理，不建议继续观察。"
    if state.concern_level.value == "moderate":
        return "【需要重视】这些变化需要尽快让医生评估。"
    if state.concern_level.value == "low":
        return "【暂时不属于急救级】目前先观察，但要留意有没有新的变化。"
    return "【信息还不够】我先确认一个会影响判断的问题。"



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
    warning_text = "、".join(warning_signs[:4]) if warning_signs else "目前没有明确急救级红旗"

    if state.concern_level.value == "high":
        return f"【为什么要马上动】我看到的关键变化是：{warning_text}。重点是尽快确认是否存在危险情况。"
    if state.concern_level.value == "moderate":
        return "【为什么不能拖】这些变化需要专业评估。现在不适合只等它自己好。"
    if state.concern_level.value == "low":
        return "【为什么现在先观察】目前没有识别到明确高风险模式。请继续观察有没有新变化或加重。"
    return "【为什么还不能下结论】现在信息还不够，不能直接说没事。"


def build_clarification_response(state: CaseState, question: str) -> ElderResponse:
    """Build a single-question response without changing question selection."""
    return ElderResponse(
        empathy_statement="还需要补充一个关键信息。",
        key_signs_summary=build_key_signs_summary(state),
        what_this_means="现在不能只凭这些信息判断具体原因。这个问题是为了判断是否需要更快就医。",
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
