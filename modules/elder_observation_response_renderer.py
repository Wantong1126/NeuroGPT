# SPDX-License-Identifier: MIT
"""Unified elder-facing rendering from accumulated observation state."""
from __future__ import annotations

from typing import Any

ESCALATION_ACTIONS = {"emergency_now", "same_day_review"}
FORBIDDEN_DIAGNOSIS_WORDING = (
    "你可能是", "疑似", "确诊", "你这是", "胃炎", "心梗", "胆囊炎", "脑梗", "肿瘤", "癌症",
)


def render_elder_observation_response(
    active_observation: dict,
    latest_user_input: str,
    next_question: str | None,
    action_level: str | None = None,
    response_mode: str = "initial",
) -> str:
    """Render a concrete response without allowing wording to alter safety action."""
    observation = active_observation or {}
    acknowledgement = _acknowledgement(observation, latest_user_input, response_mode)
    explanation = _validated_model_explanation(observation) or _domain_explanation(observation)

    parts = [acknowledgement, explanation]
    if next_question:
        parts.append(f"请您再告诉我：{_single_question(next_question)}")
    elif response_mode == "complete":
        parts.append("我已经帮您把情况记录下来了，会提醒护理员尽快确认。")

    if response_mode == "urgent" or action_level in ESCALATION_ACTIONS:
        parts.append("请马上叫护理员过来看一下。")

    response = "".join(part for part in parts if part)
    return _fit_response(response, observation, next_question, action_level, response_mode)


def _acknowledgement(observation: dict[str, Any], latest_user_input: str, mode: str) -> str:
    if mode in {"merge", "complete"} or (
        mode == "urgent" and (observation.get("answer_history") or observation.get("body_location"))
    ):
        return f"已记录：{_known_issue(observation)}。"
    report = _display_report(observation.get("raw_quote") or latest_user_input or observation.get("specific_problem", ""))
    return f"我听到您说{report}。"


def _known_issue(observation: dict[str, Any]) -> str:
    domain = observation.get("domain", "general")
    location = observation.get("body_location") or ""
    quality = (observation.get("sensation_quality") or "").replace("、", "和")
    if domain == "abdominal_digestive":
        return f"{location or '腹部'}{quality or '不舒服'}"
    if location and quality:
        return f"{location}{quality}"
    return _display_report(observation.get("raw_quote") or observation.get("specific_problem", "有些不舒服"))


def _domain_explanation(observation: dict[str, Any]) -> str:
    domain = observation.get("domain", "general")
    raw = observation.get("raw_quote", "")
    problem = observation.get("specific_problem", "")
    location = observation.get("body_location") or ""
    quality = observation.get("sensation_quality") or ""

    if domain == "abdominal_digestive":
        if "上腹" in location and "痛" in quality and "胀" in quality:
            return (
                "上腹又痛又胀可能和胃部不适、消化不良、胀气或饮食有关，但如果持续加重、伴随发热呕吐、"
                "胸闷出汗或黑便血便，需要尽快让护理员查看。"
            )
        if "上腹" in location:
            return "上腹痛有时可能和胃部不适、消化不良、胀气、受凉、饮食或药物有关，也要留意是否突然加重。"
        if not location and ("突然" in raw or "非常痛" in raw or "剧烈" in raw):
            return "肚子突然明显疼痛可能和胃肠不适、饮食、受凉、胀气或其他身体变化有关，但需要先确认位置和有没有加重。"
        return (
            "腹部不适可能和饮食、消化不良、胀气、受凉、便秘、腹泻、胃部不适或药物有关。"
            "如果疼痛持续加重，或伴随发热、呕吐、腹泻、胸闷气短、出汗、晕倒、黑便或血便，需要尽快让护理员查看。"
        )
    if domain == "sleep" or "睡" in problem:
        return "睡不好可能和起夜、身体不舒服、心里惦记事、疼痛、白天活动少或环境有关，需要护理员结合实际情况再确认。"
    if _is_musculoskeletal(observation):
        return "酸痛可能和睡姿、久坐、活动后肌肉酸痛或受凉、关节不适有关，也要留意有没有摔倒或突然加重。"
    if _is_headache(observation):
        return "头痛可能和休息不好、紧张、受凉、血压波动或身体其他不适有关，但不能据此判断具体原因。"
    if domain == "sensory" or "麻木" in problem or "发麻" in problem:
        return "手麻有时和姿势压迫、局部受凉或手脚劳累有关，也需要确认是不是突然出现或伴随没力。"
    if domain == "mood" or "不想麻烦" in raw:
        return "很多老人身体不舒服或心里有事时会先忍着，但护理员知道后才能更好照顾您。"
    if domain in {"appetite", "digestion", "appetite_digestion"}:
        return "胃口和消化变化可能和饮食、药物、睡眠、情绪或身体不舒服有关，需要护理员结合实际情况再确认。"
    return "我先帮您把这个具体情况记下来，需要再了解一点，护理员才能更好判断。"


def _validated_model_explanation(observation: dict[str, Any]) -> str | None:
    candidate = str(observation.get("possible_reasons_plain") or "").strip()
    if not candidate or len(candidate) > 180:
        return None
    if any(term in candidate for term in FORBIDDEN_DIAGNOSIS_WORDING):
        return None
    if "多种原因" in candidate or "多种常见原因" in candidate:
        return None
    if not any(term in candidate for term in ("可能和", "可能与", "需要", "护理员")):
        return None
    why = str(observation.get("why_this_matters") or "").strip()
    if why and len(why) <= 100 and not any(term in why for term in FORBIDDEN_DIAGNOSIS_WORDING):
        candidate = f"{candidate.rstrip('。')}。{why}"
    return candidate if candidate.endswith("。") else f"{candidate}。"


def _is_musculoskeletal(observation: dict[str, Any]) -> bool:
    location = observation.get("body_location") or ""
    problem = observation.get("specific_problem") or ""
    return observation.get("domain") == "musculoskeletal_pain" or (
        observation.get("domain") == "pain"
        and any(term in f"{location}{problem}" for term in ("肩", "背", "腰", "胳膊", "腿", "关节", "肌肉"))
    )


def _is_headache(observation: dict[str, Any]) -> bool:
    return observation.get("domain") == "headache" or "头" in (observation.get("body_location") or "") or any(
        term in f"{observation.get('specific_problem', '')}{observation.get('raw_quote', '')}" for term in ("头痛", "头疼")
    )


def _display_report(report: str) -> str:
    text = str(report).strip().rstrip("。.!！")
    if text.startswith("我") and len(text) > 1:
        text = text[1:].lstrip("，, ")
    return text or "有些不舒服"


def _single_question(question: str) -> str:
    text = question.strip().rstrip("。.!！?？")
    text = text.replace("？", "，").replace("?", "，")
    return f"{text.rstrip('，, ')}？"


def _fit_response(
    response: str,
    observation: dict[str, Any],
    question: str | None,
    action_level: str | None,
    mode: str,
) -> str:
    if len(response) <= 320 or mode == "urgent" or action_level in ESCALATION_ACTIONS:
        return response
    acknowledgement = _acknowledgement(observation, "", mode)
    explanation = _domain_explanation(observation)
    suffix = f"请您再告诉我：{_single_question(question)}" if question else "我已经记录下来，会提醒护理员确认。"
    available = 320 - len(acknowledgement) - len(suffix)
    if available <= 0:
        return f"{acknowledgement}{suffix}"[:320]
    return f"{acknowledgement}{_truncate(explanation, available)}{suffix}"[:320]


def _truncate(text: str, length: int) -> str:
    if len(text) <= length:
        return text
    return f"{text[:max(1, length - 1)].rstrip('，,；;。 ')}…"
