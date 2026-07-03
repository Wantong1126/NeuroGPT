# SPDX-License-Identifier: MIT
"""Deterministic routing from elder wording to broad question families."""
from __future__ import annotations

from typing import Literal

SymptomFamily = Literal[
    "musculoskeletal_pain",
    "headache",
    "numbness_or_weakness",
    "dizziness",
    "sleep",
    "mood_loneliness",
    "memory_language",
    "gait_fall",
    "appetite_digestion",
    "chest_breathing",
    "general_unclear",
]


def route_symptom_family(user_input: str) -> SymptomFamily:
    """Route wording only; this function does not assess risk or choose action."""
    text = (user_input or "").strip().lower()

    if _has_any(text, ("胸闷", "胸痛", "胸口疼", "气短", "喘不上气", "呼吸困难")):
        return "chest_breathing"
    if _has_any(text, ("手麻", "脚麻", "腿麻", "麻木", "发麻", "没力", "没力气", "无力", "动不了", "脸歪", "嘴歪")):
        return "numbness_or_weakness"
    if _has_any(text, ("头痛", "头疼", "头很痛", "头突然疼", "头突然很痛")):
        return "headache"
    if _has_any(text, ("头晕", "眩晕", "眼前发黑", "天旋地转")):
        return "dizziness"
    if _has_any(text, ("不想麻烦孩子", "不想麻烦家人", "孤单", "没意思", "心情不好", "不想见人")):
        return "mood_loneliness"
    if _has_any(text, ("睡不好", "睡不着", "失眠", "醒很多次", "半夜总醒", "总是醒")):
        return "sleep"
    if _has_any(text, ("记不住", "忘事", "记忆", "糊涂", "不认人", "说话不清", "表达困难", "说不出话")):
        return "memory_language"
    if _has_any(text, ("走不稳", "走路不稳", "容易摔倒", "摔倒", "跌倒", "站不稳")):
        return "gait_fall"
    if _has_any(text, ("没胃口", "不想吃", "吃不下", "肚子痛", "肚子疼", "恶心", "呕吐", "拉肚子", "便秘")):
        return "appetite_digestion"
    if _has_musculoskeletal_pain(text):
        return "musculoskeletal_pain"
    return "general_unclear"


def _has_musculoskeletal_pain(text: str) -> bool:
    body_area = _has_any(text, ("肩膀", "肩", "背", "腰", "腿", "胳膊", "关节", "肌肉"))
    pain_word = _has_any(text, ("酸", "酸痛", "疼", "痛"))
    return body_area and pain_word


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)
