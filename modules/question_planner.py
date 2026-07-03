# SPDX-License-Identifier: MIT
"""Question planning for deterministic symptom families."""
from __future__ import annotations

from modules.symptom_family_router import SymptomFamily

FAMILY_QUESTIONS: dict[SymptomFamily, str] = {
    "musculoskeletal_pain": "这种酸痛是今天刚出现，还是已经持续几天了；有没有摔倒、胸闷、气短、出汗，或者疼痛越来越重？",
    "headache": "头痛是突然一下子很严重，还是慢慢开始的；有没有呕吐、看不清、说话不清，或者手脚没力？",
    "numbness_or_weakness": "这种感觉是在一边还是两边，是突然出现的，还是慢慢出现的；有没有说话不清、脸歪或明显没力？",
    "dizziness": "头晕是突然出现的，还是慢慢开始的；有没有站不稳、呕吐、胸闷或眼前发黑？",
    "sleep": "是入睡困难，还是半夜醒很多次；这种情况连续几天了？",
    "mood_loneliness": "您是不舒服但不想麻烦家人，还是最近心情不好、想一个人待着？",
    "memory_language": "记忆或说话的变化是突然出现的，还是慢慢发生的；最近有没有明显加重？",
    "gait_fall": "走路不稳是今天刚出现的吗；有没有摔倒、撞到头、头晕或一边手脚没力？",
    "appetite_digestion": "是没有胃口，还是吃了以后不舒服；有没有持续呕吐、腹痛加重或便血？",
    "chest_breathing": "胸闷、胸痛或气短是突然出现的吗；现在有没有出汗、头晕或越来越严重？",
    "general_unclear": "这个情况是今天刚出现的吗；现在有没有比刚开始更严重？",
}


def plan_follow_up_question(family: SymptomFamily) -> str:
    return FAMILY_QUESTIONS[family]
