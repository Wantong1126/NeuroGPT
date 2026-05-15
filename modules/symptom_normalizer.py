# SPDX-License-Identifier: MIT
"""Lay-language symptom normalization.

This module is the single deterministic place where everyday user wording is
mapped into broad internal symptom signals. Action-tier decisions remain in the
rule engine; this layer only normalizes wording into structured signals.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.types import Laterality, Onset, Progression


def _has_any(text: str, phrases: list[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def _has_worsening(text: str) -> bool:
    return _has_any(text, WORSENING_PHRASES) and not _has_any(text, STABLE_PHRASES)


SUDDEN_PHRASES = [
    "突然",
    "忽然",
    "一下子",
    "刚才",
    "刚刚",
    "今早",
    "今天早上",
    "今天突然",
    "sudden",
    "suddenly",
    "this morning",
]

GRADUAL_PHRASES = [
    "慢慢",
    "逐渐",
    "越来越",
    "几周",
    "几个月",
    "gradual",
    "gradually",
    "slowly",
    "over weeks",
    "over months",
]

CHRONIC_PHRASES = [
    "这几年",
    "几年",
    "多年",
    "长期",
    "一直",
    "for years",
    "years",
    "longstanding",
    "chronic",
]

WORSENING_PHRASES = [
    "加重",
    "恶化",
    "越来越",
    "更严重",
    "worsening",
    "getting worse",
]

STABLE_PHRASES = [
    "没有加重",
    "没加重",
    "没有变重",
    "稳定",
    "一直这样",
    "not worse",
    "no worse",
    "stable",
]

RIGHT_SIDE_PHRASES = ["右", "右手", "右脚", "右腿", "右边", "right"]
LEFT_SIDE_PHRASES = ["左", "左手", "左脚", "左腿", "左边", "left"]
ONE_SIDE_PHRASES = [
    "一侧",
    "一边",
    "单侧",
    "半边",
    "半身",
    "one side",
    "one-sided",
    "unilateral",
]
BOTH_SIDE_PHRASES = ["两边", "双侧", "双手", "双腿", "both sides", "bilateral"]

WEAKNESS_PHRASES = [
    "没力",
    "没力气",
    "无力",
    "抬不起来",
    "动不了",
    "weak",
    "weakness",
    "cannot move",
    "can't move",
]

FACIAL_ASYMMETRY_PHRASES = [
    "嘴歪",
    "脸歪",
    "脸不对称",
    "面部不对称",
    "口角歪",
    "面瘫",
    "facial droop",
    "face droop",
    "droopy",
    "drooping",
    "facial asymmetry",
]

SENSORY_PHRASES = [
    "麻木",
    "发麻",
    "半边身子麻",
    "身子麻",
    "numb",
    "numbness",
    "tingling",
]

SPEECH_SLUR_PHRASES = [
    "讲话不清",
    "说话不清",
    "口齿不清",
    "含糊",
    "说不清",
    "slurred",
    "speech is unclear",
]

WORD_FINDING_PHRASES = [
    "表达困难",
    "表达有点困难",
    "找词困难",
    "叫不出名字",
    "说不出话",
    "不会说话",
    "word finding",
    "word-finding",
    "cannot get words out",
    "can't get words out",
    "cannot speak",
    "can't speak",
    "aphasia",
]

SPEECH_LANGUAGE_PHRASES = [
    *SPEECH_SLUR_PHRASES,
    *WORD_FINDING_PHRASES,
    "说话慢",
    "说话越来越慢",
    "trouble speaking",
    "trouble expressing",
]

NON_NEURO_EXPRESSION_REQUEST_PHRASES = [
    "我不知道怎么表达这个症状",
    "我不知道怎么描述这个症状",
    "不知道怎么表达这个症状",
    "不知道怎么描述这个症状",
    "不知道该怎么表达",
    "不知道该怎么描述",
    "don't know how to express",
    "do not know how to express",
    "don't know how to describe",
    "do not know how to describe",
]

CONFUSION_AWARENESS_PHRASES = [
    "糊涂",
    "混乱",
    "不认人",
    "意识不清",
    "神志不清",
    "叫不醒",
    "反应很慢",
    "confusion",
    "confused",
    "disoriented",
    "does not recognize",
    "not recognize",
    "hard to wake",
    "altered awareness",
]

MEMORY_COGNITIVE_PHRASES = [
    "记忆",
    "忘事",
    "记不住",
    "认知",
    "memory",
    "cognitive",
    "dementia",
]

GAIT_BALANCE_PHRASES = [
    "走路不稳",
    "步态",
    "平衡差",
    "平衡不好",
    "容易摔倒",
    "gait",
    "imbalance",
    "balance",
    "unsteady",
]

HEADACHE_PHRASES = [
    "头痛",
    "剧烈头痛",
    "爆炸样头痛",
    "雷击样头痛",
    "headache",
    "severe headache",
    "thunderclap",
]

VISION_PHRASES = [
    "看不见",
    "看不清",
    "视力",
    "复视",
    "重影",
    "vision",
    "vision loss",
    "blind",
    "double vision",
]

SEIZURE_PHRASES = [
    "抽搐",
    "癫痫",
    "翻白眼",
    "口吐白沫",
    "seizure",
    "convulsion",
    "fit",
]

LOSS_OF_CONSCIOUSNESS_PHRASES = [
    "昏迷",
    "失去意识",
    "晕倒",
    "叫不醒",
    "unconscious",
    "passed out",
    "lost consciousness",
    "blackout",
]

FALL_PHRASES = ["跌倒", "摔倒", "摔了一跤", "fall", "falls", "fell"]
HEAD_INJURY_PHRASES = ["摔到头", "撞到头", "头部受伤", "head injury", "hit head"]
INCONTINENCE_PHRASES = ["失禁", "大小便失禁", "incontinence"]
TREMOR_PHRASES = ["手抖", "震颤", "tremor"]
STIFFNESS_PHRASES = ["僵硬", "stiffness"]
HALLUCINATION_PHRASES = ["幻觉", "看到不存在", "hallucination"]
PERSONALITY_PHRASES = ["性格改变", "脾气变", "personality change"]


@dataclass(frozen=True)
class NormalizedSymptomSignals:
    raw_text: str
    weakness_possible: bool = False
    facial_asymmetry_possible: bool = False
    sensory_possible: bool = False
    speech_language_possible: bool = False
    speech_slurring_possible: bool = False
    word_finding_possible: bool = False
    confusion_awareness_possible: bool = False
    memory_cognitive_possible: bool = False
    gait_balance_possible: bool = False
    headache_possible: bool = False
    vision_possible: bool = False
    seizure_episode_possible: bool = False
    loss_of_consciousness_possible: bool = False
    fall_head_injury_possible: bool = False
    fall_possible: bool = False
    head_injury_possible: bool = False
    incontinence_possible: bool = False
    tremor_possible: bool = False
    stiffness_possible: bool = False
    hallucination_possible: bool = False
    personality_change_possible: bool = False
    one_sided_possible: bool = False
    right_side_possible: bool = False
    left_side_possible: bool = False
    both_sides_possible: bool = False
    sudden_possible: bool = False
    gradual_possible: bool = False
    chronic_possible: bool = False
    worsening_possible: bool = False
    stable_possible: bool = False
    non_neurological_expression_request: bool = False
    matched_phrases: dict[str, list[str]] = field(default_factory=dict)

    @property
    def onset(self) -> Onset:
        if self.sudden_possible:
            return Onset.SUDDEN
        if self.chronic_possible:
            return Onset.CHRONIC
        if self.gradual_possible:
            return Onset.GRADUAL
        return Onset.UNKNOWN

    @property
    def laterality(self) -> Laterality:
        if self.both_sides_possible:
            return Laterality.BOTH_SIDES
        if self.one_sided_possible or self.right_side_possible or self.left_side_possible:
            return Laterality.ONE_SIDE
        return Laterality.UNKNOWN

    @property
    def progression(self) -> Progression:
        if self.stable_possible:
            return Progression.STABLE
        if self.worsening_possible:
            return Progression.WORSENING
        if self.onset != Onset.UNKNOWN:
            return Progression.FIRST_TIME
        return Progression.UNKNOWN

    @property
    def focal_neurologic_possible(self) -> bool:
        return (
            self.weakness_possible
            or self.facial_asymmetry_possible
            or self.sensory_possible
            or self.speech_language_possible
            or self.vision_possible
            or self.gait_balance_possible
        )

    def symptom_types(self) -> list[str]:
        symptom_types: list[str] = []
        if self.weakness_possible or self.tremor_possible:
            symptom_types.append("motor")
        if self.speech_language_possible:
            symptom_types.append("speech")
        if self.sensory_possible or self.vision_possible:
            symptom_types.append("sensory")
        if self.gait_balance_possible:
            symptom_types.append("gait")
        if self.confusion_awareness_possible or self.memory_cognitive_possible:
            symptom_types.append("cognitive")
        if self.personality_change_possible:
            symptom_types.append("behavioral")
        return symptom_types or ["other"]


def _matches(text: str, phrases: list[str]) -> list[str]:
    return [phrase for phrase in phrases if phrase in text]


def normalize_symptoms(user_input: str) -> NormalizedSymptomSignals:
    text = user_input.lower()

    matched = {
        "sudden": _matches(text, SUDDEN_PHRASES),
        "gradual": _matches(text, GRADUAL_PHRASES),
        "chronic": _matches(text, CHRONIC_PHRASES),
        "stable": _matches(text, STABLE_PHRASES),
        "worsening": _matches(text, WORSENING_PHRASES),
        "right_side": _matches(text, RIGHT_SIDE_PHRASES),
        "left_side": _matches(text, LEFT_SIDE_PHRASES),
        "one_side": _matches(text, ONE_SIDE_PHRASES),
        "both_sides": _matches(text, BOTH_SIDE_PHRASES),
        "weakness": _matches(text, WEAKNESS_PHRASES),
        "facial_asymmetry": _matches(text, FACIAL_ASYMMETRY_PHRASES),
        "sensory": _matches(text, SENSORY_PHRASES),
        "speech_slur": _matches(text, SPEECH_SLUR_PHRASES),
        "word_finding": _matches(text, WORD_FINDING_PHRASES),
        "speech_language": _matches(text, SPEECH_LANGUAGE_PHRASES),
        "non_neuro_expression_request": _matches(text, NON_NEURO_EXPRESSION_REQUEST_PHRASES),
        "confusion_awareness": _matches(text, CONFUSION_AWARENESS_PHRASES),
        "memory_cognitive": _matches(text, MEMORY_COGNITIVE_PHRASES),
        "gait_balance": _matches(text, GAIT_BALANCE_PHRASES),
        "headache": _matches(text, HEADACHE_PHRASES),
        "vision": _matches(text, VISION_PHRASES),
        "seizure": _matches(text, SEIZURE_PHRASES),
        "loss_of_consciousness": _matches(text, LOSS_OF_CONSCIOUSNESS_PHRASES),
        "fall": _matches(text, FALL_PHRASES),
        "head_injury": _matches(text, HEAD_INJURY_PHRASES),
        "incontinence": _matches(text, INCONTINENCE_PHRASES),
        "tremor": _matches(text, TREMOR_PHRASES),
        "stiffness": _matches(text, STIFFNESS_PHRASES),
        "hallucination": _matches(text, HALLUCINATION_PHRASES),
        "personality": _matches(text, PERSONALITY_PHRASES),
    }

    speech_language_possible = bool(matched["speech_language"])
    non_neuro_expression_request = bool(matched["non_neuro_expression_request"]) and not speech_language_possible
    facial_asymmetry_possible = bool(matched["facial_asymmetry"])
    sensory_possible = bool(matched["sensory"])
    fall_possible = bool(matched["fall"])
    head_injury_possible = bool(matched["head_injury"])

    return NormalizedSymptomSignals(
        raw_text=user_input,
        weakness_possible=bool(matched["weakness"]),
        facial_asymmetry_possible=facial_asymmetry_possible,
        sensory_possible=sensory_possible,
        speech_language_possible=False if non_neuro_expression_request else speech_language_possible,
        speech_slurring_possible=False if non_neuro_expression_request else bool(matched["speech_slur"]),
        word_finding_possible=False if non_neuro_expression_request else bool(matched["word_finding"]),
        confusion_awareness_possible=bool(matched["confusion_awareness"]),
        memory_cognitive_possible=bool(matched["memory_cognitive"]),
        gait_balance_possible=bool(matched["gait_balance"]),
        headache_possible=bool(matched["headache"]),
        vision_possible=bool(matched["vision"]),
        seizure_episode_possible=bool(matched["seizure"]),
        loss_of_consciousness_possible=bool(matched["loss_of_consciousness"]),
        fall_head_injury_possible=fall_possible or head_injury_possible,
        fall_possible=fall_possible,
        head_injury_possible=head_injury_possible,
        incontinence_possible=bool(matched["incontinence"]),
        tremor_possible=bool(matched["tremor"]),
        stiffness_possible=bool(matched["stiffness"]),
        hallucination_possible=bool(matched["hallucination"]),
        personality_change_possible=bool(matched["personality"]),
        one_sided_possible=bool(matched["one_side"]) or facial_asymmetry_possible or "半边身子麻" in text,
        right_side_possible=bool(matched["right_side"]),
        left_side_possible=bool(matched["left_side"]),
        both_sides_possible=bool(matched["both_sides"]),
        sudden_possible=bool(matched["sudden"]),
        gradual_possible=bool(matched["gradual"]),
        chronic_possible=bool(matched["chronic"]),
        worsening_possible=_has_worsening(text),
        stable_possible=bool(matched["stable"]),
        non_neurological_expression_request=non_neuro_expression_request,
        matched_phrases={key: value for key, value in matched.items() if value},
    )
