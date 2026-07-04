# SPDX-License-Identifier: MIT
"""Natural elder-facing explanations with deterministic safety boundaries."""
from __future__ import annotations

import json

from pydantic import BaseModel

from core.llm import call_structured
from core.provider_settings import (
    get_provider,
    get_provider_base_url,
    get_provider_model,
)
from core.types import CaseState
from modules.symptom_family_router import SymptomFamily

SYSTEM_PROMPT = """
你负责把已经确定的照护提示改写成简短、自然、适合中国老人的中文。
你只能解释常见可能原因和表达关心，不能诊断，不能更改 action_level，不能降低紧急程度。
不要提到模型、规则、风险分级或内部字段。不要输出家属或护理员内部摘要。
planned_follow_up_question 中的安全要点必须保留。除紧急情况外，总文字应控制在 180 个汉字以内。
""".strip()

SCHEMA = """
{
  "acknowledgement": "简短复述老人原话",
  "possible_reasons_plain": "用不确定语气说明常见可能原因，不作诊断",
  "next_question": "自然表达给定的关键追问",
  "when_to_call_staff": "什么情况下马上叫护理员"
}
"""

URGENT_STAFF_TEXT = "请马上叫护理员过来看一下。"
FORBIDDEN_DIAGNOSIS_PHRASES = (
    "确诊",
    "诊断为",
    "一定是",
    "就是脑",
    "患有",
    "中风",
    "脑梗",
    "脑出血",
    "心梗",
)


class ElderExplanation(BaseModel):
    acknowledgement: str
    possible_reasons_plain: str
    next_question: str = ""
    when_to_call_staff: str


def generate_elder_explanation(
    state: CaseState,
    symptom_family: SymptomFamily,
    action_level: str,
    planned_follow_up_question: str | None,
) -> ElderExplanation:
    """Generate wording only; deterministic state and action are never mutated."""
    fallback = _fallback_explanation(
        state,
        symptom_family,
        action_level,
        planned_follow_up_question,
    )
    if get_provider("elder_explanation_generator") != "openai_compatible":
        return fallback

    prompt = _build_prompt(
        state,
        symptom_family,
        action_level,
        planned_follow_up_question,
    )
    try:
        raw = call_structured(
            prompt,
            SYSTEM_PROMPT,
            SCHEMA,
            model=get_provider_model("elder_explanation_generator") or None,
            base_url=get_provider_base_url("elder_explanation_generator") or None,
        )
        explanation = _validated_explanation(
            raw,
            fallback,
            action_level,
            planned_follow_up_question,
        )
    except Exception:
        return fallback
    return explanation


def format_elder_explanation(explanation: ElderExplanation) -> str:
    parts = [explanation.acknowledgement, explanation.possible_reasons_plain]
    if explanation.next_question:
        parts.append(f"请您再告诉我：{explanation.next_question}")
    parts.append(explanation.when_to_call_staff)
    return "".join(part.strip() for part in parts if part and part.strip())


def _build_prompt(
    state: CaseState,
    symptom_family: SymptomFamily,
    action_level: str,
    planned_follow_up_question: str | None,
) -> str:
    payload = {
        "raw_report": state.raw_user_input,
        "symptom_family": symptom_family,
        "deterministic_action_level": action_level,
        "planned_follow_up_question": planned_follow_up_question or "",
        "known_red_flags": _known_red_flags(state),
        "requirements": [
            "不诊断，只说明常见可能原因",
            "不得改变或弱化 deterministic_action_level",
            "紧急时必须包含：请马上叫护理员过来看一下。",
            "非紧急总文字不超过180个汉字",
        ],
    }
    return "请根据以下确定性结果生成老人可读说明：\n" + json.dumps(payload, ensure_ascii=False)


def _validated_explanation(
    raw: object,
    fallback: ElderExplanation,
    action_level: str,
    planned_follow_up_question: str | None,
) -> ElderExplanation:
    if not isinstance(raw, dict):
        return fallback
    values = {
        key: str(raw.get(key) or "").strip()
        for key in ("acknowledgement", "possible_reasons_plain", "next_question", "when_to_call_staff")
    }
    if not values["acknowledgement"] or not values["possible_reasons_plain"]:
        return fallback
    generated_advice = values["possible_reasons_plain"] + values["when_to_call_staff"]
    if any(phrase in generated_advice for phrase in FORBIDDEN_DIAGNOSIS_PHRASES):
        return fallback
    if "我听到您说" not in values["acknowledgement"]:
        values["acknowledgement"] = fallback.acknowledgement

    # The deterministic planner owns the safety content of the next question.
    values["next_question"] = _first_question(planned_follow_up_question)
    if action_level == "emergency_now":
        values["possible_reasons_plain"] = fallback.possible_reasons_plain
        if URGENT_STAFF_TEXT not in values["when_to_call_staff"]:
            values["when_to_call_staff"] = URGENT_STAFF_TEXT
    elif not values["when_to_call_staff"]:
        values["when_to_call_staff"] = fallback.when_to_call_staff

    explanation = ElderExplanation(**values)
    if action_level != "emergency_now" and len(format_elder_explanation(explanation)) > 180:
        return fallback
    return explanation


def _fallback_explanation(
    state: CaseState,
    symptom_family: SymptomFamily,
    action_level: str,
    planned_follow_up_question: str | None,
) -> ElderExplanation:
    report = (state.raw_user_input or "您有些不舒服").strip().rstrip("。.!！")
    return ElderExplanation(
        acknowledgement=f"我听到您说：{report}。",
        possible_reasons_plain=(
            "这些突然出现的变化需要马上请人查看，先不要自行判断原因。"
            if action_level == "emergency_now"
            else _fallback_possible_reasons(symptom_family)
        ),
        next_question=_first_question(planned_follow_up_question),
        when_to_call_staff=_fallback_staff_advice(symptom_family, action_level),
    )


def _fallback_possible_reasons(family: SymptomFamily) -> str:
    reasons: dict[SymptomFamily, str] = {
        "musculoskeletal_pain": "这种情况可能和姿势、活动后肌肉酸痛、受凉或休息不好有关，也可能只是短暂不适。",
        "headache": "这种情况可能和休息不好、紧张、受凉或血压波动有关，也可能只是短暂不适。",
        "numbness_or_weakness": "这种情况可能和姿势压迫、劳累或活动后不适有关，也需要留意是不是突然出现。",
        "dizziness": "这种情况可能和起身太快、休息不好、进食少或血压波动有关。",
        "sleep": "这种情况可能和作息、环境、白天活动、心情或身体不舒服有关。",
        "mood_loneliness": "这种感受可能和孤单、担心家人、休息不好或最近遇到的事情有关。",
        "memory_language": "这种变化可能和疲劳、睡眠、情绪或身体状态有关，也需要看看是否持续加重。",
        "gait_fall": "这种情况可能和腿脚乏力、头晕、疼痛或平衡变化有关。",
        "appetite_digestion": "这种情况可能和饮食、消化、药物或休息不好有关。",
        "chest_breathing": "这种情况可能和活动、紧张或身体不适有关，需要尽快确认有没有加重。",
        "general_unclear": "我先帮您把这个具体情况记下来，还需要再了解一点。",
    }
    return reasons[family]


def _fallback_staff_advice(family: SymptomFamily, action_level: str) -> str:
    if action_level == "emergency_now":
        return URGENT_STAFF_TEXT
    if action_level in {"same_day_review", "prompt_clinical_review", "prompt_follow_up"}:
        return "如果不舒服加重或又出现新的变化，请马上叫护理员。"
    family_advice = {
        "musculoskeletal_pain": "如果疼痛突然加重，或伴有胸闷、气短、出汗，请马上叫护理员。",
        "headache": "如果头痛突然很重，或出现呕吐、看不清、说话不清、手脚没力，请马上叫护理员。",
        "numbness_or_weakness": "如果突然一边麻木或没力，或出现脸歪、说话不清，请马上叫护理员。",
        "dizziness": "如果突然站不稳、昏倒、说话不清或一边没力，请马上叫护理员。",
        "sleep": "如果连续多天睡不好，或白天明显不舒服，请告诉护理员。",
        "mood_loneliness": "如果心里很难受，或有伤害自己的想法，请马上告诉护理员。",
    }
    return family_advice.get(family, "如果情况加重或出现新的不舒服，请马上叫护理员。")


def _known_red_flags(state: CaseState) -> list[str]:
    red_flags = state.symptoms_detected.red_flags
    candidates = (
        (red_flags.weakness_one_side, "单侧无力"),
        (red_flags.facial_droop, "脸歪"),
        (red_flags.slurred_speech, "说话不清"),
        (red_flags.acute_confusion, "突然糊涂"),
        (red_flags.seizure, "抽搐"),
        (red_flags.loss_of_consciousness, "意识丧失"),
        (red_flags.severe_headache, "剧烈头痛"),
        (red_flags.vision_loss, "突然看不见"),
    )
    return [label for present, label in candidates if present]


def _first_question(question: str | None) -> str:
    if not question:
        return ""
    positions = [position for marker in ("？", "?") if (position := question.find(marker)) >= 0]
    return question[: min(positions) + 1] if positions else question
