# SPDX-License-Identifier: MIT
"""Unified elder-facing rendering from accumulated observation state."""
from __future__ import annotations

from typing import Any, TypedDict

ESCALATION_ACTIONS = {"emergency_now", "same_day_review"}
FORBIDDEN_DIAGNOSIS_WORDING = (
    "你可能是", "疑似", "确诊", "你这是", "胃炎", "心梗", "胆囊炎", "脑梗", "肿瘤", "癌症",
)


class ElderExplanationParts(TypedDict):
    plain_possible_reasons: str
    safe_mitigation: str
    direct_red_flag_question: str
    staff_only_checks: list[str]


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
    detail = _response_detail(observation)
    explanation = _validated_model_explanation(observation) or detail["plain_possible_reasons"]

    parts = [acknowledgement, explanation, detail["safe_mitigation"]]
    if next_question:
        parts.append(f"请您再告诉我：{_single_question(next_question)}")
    elif detail["direct_red_flag_question"] and response_mode not in {"complete", "urgent"}:
        parts.append(f"请您再告诉我：{_single_question(detail['direct_red_flag_question'])}")
    elif response_mode == "complete":
        parts.append("我已经帮您把情况记录下来了，会把这条记录给护理员看。")

    if response_mode == "urgent" or action_level in ESCALATION_ACTIONS:
        parts.append("这个情况需要护理员尽快过来看一下。请马上叫护理员过来看一下。")

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
        location = location.replace("背部", "背").replace("腰部", "腰")
        duration = observation.get("duration") or ""
        return f"{location}{quality}{duration if _is_musculoskeletal(observation) else ''}"
    return _display_report(observation.get("raw_quote") or observation.get("specific_problem", "有些不舒服"))


def _response_detail(observation: dict[str, Any]) -> ElderExplanationParts:
    domain = observation.get("domain", "general")
    raw = observation.get("raw_quote", "")
    problem = observation.get("specific_problem", "")
    location = observation.get("body_location") or ""
    quality = observation.get("sensation_quality") or ""

    if domain == "abdominal_digestive":
        if "上腹" in location and "痛" in quality and "胀" in quality:
            reasons = "上腹又痛又胀可能和胃部不适、消化不良、胀气、饮食刺激、受凉或药物有关。"
        elif "上腹" in location:
            reasons = "上腹不舒服有时可能和胃部不适、消化不良、胀气、饮食刺激、受凉或药物有关。"
        elif not location and ("突然" in raw or "非常痛" in raw or "剧烈" in raw):
            reasons = "肚子突然明显疼痛可能和胃肠不适、饮食刺激、受凉、胀气、便秘或腹泻有关，但需要尽快确认具体位置。"
        else:
            reasons = "腹部不适可能和饮食刺激、消化不良、胀气、受凉、便秘、腹泻、胃部不适或药物有关。"
        return {
            "plain_possible_reasons": reasons,
            "safe_mitigation": "您先不要硬撑着活动，也先别自行吃药，可以坐下或躺在舒服的位置等护理员确认。",
            "direct_red_flag_question": "疼痛有没有越来越重，或者有没有发热、呕吐、胸闷气短、出汗、晕倒、黑便或血便？",
            "staff_only_checks": ["腹部位置和硬度", "进食饮水情况", "发热、呕吐、腹泻、黑便或血便"],
        }
    if domain == "sleep" or "睡" in problem:
        return _parts(
            "睡不好可能和起夜、身体不舒服、心里惦记事有关；具体可能是夜里起夜或疼痛、白天活动少，或者房间太亮、太吵、太冷太热。",
            "您先把昨晚醒来的次数和哪里不舒服告诉护理员，白天尽量按平时作息休息。",
        )
    if _is_musculoskeletal(observation):
        if "肩" in location and "背" in location and "酸" in quality:
            reasons = "肩背酸痛有时和昨晚睡姿不舒服、低头久坐、肩背受凉，或者前一天活动后肌肉酸痛有关。"
            mitigation = "您先放松肩背，避免继续弯腰或提重物，可以坐下休息，保持舒服姿势。"
        elif "背" in location or "腰" in location:
            reasons = (
                "早上起床后背痛，有时和昨晚睡姿不舒服、床垫或枕头支撑不好、翻身少、久坐后腰背僵硬，"
                "或者前一天弯腰、提东西、走路多造成肌肉酸痛有关。"
            )
            mitigation = "您先别硬撑着活动或弯腰提重物，可以先坐下休息，保持舒服姿势。"
        else:
            reasons = "这处酸痛有时和睡姿不舒服、同一姿势保持太久、受凉，或者前一天活动后肌肉和关节疲劳有关。"
            mitigation = "您先别硬撑着活动，避免弯腰或提重物，可以坐下休息，保持舒服姿势。"
        return {
            "plain_possible_reasons": reasons,
            "safe_mitigation": mitigation,
            "direct_red_flag_question": "今天有没有摔倒、扭到，或者疼痛是突然一下子很重、越来越重？",
            "staff_only_checks": [
                "是否摔倒、扭伤、搬重物或活动后加重",
                "疼痛部位和性质",
                "是否影响站立、走路、翻身或吃饭",
                "是否伴随胸闷、气短、出汗、发热、麻木或无力",
            ],
        }
    if _is_headache(observation):
        return _parts(
            "头痛有时和昨晚休息不好、心里紧张、头颈受凉、血压波动或身体其他不舒服有关，但不能据此判断具体原因。",
            "您先坐下休息，别突然起身或独自走远。",
            "头痛是不是突然一下子很重，有没有呕吐、看不清、说话不清或手脚没力？",
        )
    if domain == "sensory" or "麻木" in problem or "发麻" in problem:
        return _parts(
            "手脚发麻有时和睡觉或坐着时压住手脚、局部受凉，或者手脚活动太久有关。",
            "您先坐稳，不要勉强用发麻的手脚拿重物或独自走动。",
            "这种麻木是不是突然出现，有没有同时没力、脸歪或说话不清？",
        )
    if domain == "mood" or "不想麻烦" in raw:
        return _parts(
            "很多老人身体不舒服或心里有事时会先忍着，但护理员知道后才能更好照顾您。",
            "您不用一个人扛着，可以先告诉护理员是身体哪里不舒服，还是心里难受。",
        )
    if domain in {"appetite", "digestion", "appetite_digestion"}:
        return _parts(
            "胃口和消化变化有时和最近吃的东西、药物、睡眠、心情或身体不舒服有关。",
            "您先不要勉强吃太多，把能不能喝水、有没有恶心或腹泻告诉护理员。",
        )
    return _parts(
        "我先帮您把这个具体情况记下来，还需要知道什么时候开始、有没有加重，护理员才能更清楚地了解。",
        "您先坐下休息，不要硬撑；如果现在明显更不舒服，请直接叫护理员。",
    )


def _parts(reasons: str, mitigation: str, direct_question: str = "") -> ElderExplanationParts:
    return {
        "plain_possible_reasons": reasons,
        "safe_mitigation": mitigation,
        "direct_red_flag_question": direct_question,
        "staff_only_checks": [],
    }


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
    if len(response) <= 420 or mode == "urgent" or action_level in ESCALATION_ACTIONS:
        return response
    acknowledgement = _acknowledgement(observation, "", mode)
    detail = _response_detail(observation)
    explanation = f"{detail['plain_possible_reasons']}{detail['safe_mitigation']}"
    suffix = f"请您再告诉我：{_single_question(question)}" if question else "我已经记录下来，会提醒护理员确认。"
    available = 420 - len(acknowledgement) - len(suffix)
    if available <= 0:
        return f"{acknowledgement}{suffix}"[:420]
    return f"{acknowledgement}{_truncate(explanation, available)}{suffix}"[:420]


def _truncate(text: str, length: int) -> str:
    if len(text) <= length:
        return text
    return f"{text[:max(1, length - 1)].rstrip('，,；;。 ')}…"
