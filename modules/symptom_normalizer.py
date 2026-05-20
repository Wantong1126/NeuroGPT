# SPDX-License-Identifier: MIT
"""Lay-language symptom normalization.

This module is the single deterministic place where everyday user wording is
mapped into broad internal symptom signals. Action-tier decisions remain in the
rule engine; this layer only normalizes wording into structured signals.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.observations import NormalizedObservation
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
    "手麻",
    "腿麻",
    "脚麻",
    "有点麻",
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
    "有点头痛",
    "头疼",
    "有点头疼",
    "headache",
]

SEVERE_HEADACHE_PHRASES = [
    "剧烈头痛",
    "爆炸样头痛",
    "雷击样头痛",
    "剧烈头疼",
    "爆炸样头疼",
    "雷击样头疼",
    "severe headache",
    "worst headache",
    "worst headache of life",
    "thunderclap",
]

VISION_CHANGE_PHRASES = [
    "看不清",
    "视力",
    "复视",
    "重影",
    "vision change",
    "vision",
    "blurred vision",
    "blurry vision",
    "double vision",
]

VISION_LOSS_PHRASES = [
    "看不见",
    "突然看不见",
    "vision loss",
    "loss of vision",
    "blind",
    "blindness",
]

TRANSIENT_OR_RESOLVED_PHRASES = [
    "一下",
    "现在好了",
    "站起来好了",
    "站起来好多了",
    "很快好了",
    "好多了",
    "缓解了",
    "已经好了",
    "resolved",
    "went away",
    "better now",
]

FATIGUE_PHRASES = [
    "有点累",
    "今天有点累",
    "累",
    "疲劳",
    "乏力",
    "tired",
    "fatigue",
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
    severe_headache_possible: bool = False
    vision_change_possible: bool = False
    vision_loss_possible: bool = False
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
    transient_or_resolved_possible: bool = False
    fatigue_possible: bool = False
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
        if self.transient_or_resolved_possible:
            return Progression.IMPROVING
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
            or self.vision_change_possible
            or self.vision_loss_possible
            or self.gait_balance_possible
        )

    def symptom_types(self) -> list[str]:
        symptom_types: list[str] = []
        if self.weakness_possible or self.tremor_possible:
            symptom_types.append("motor")
        if self.speech_language_possible:
            symptom_types.append("speech")
        if self.sensory_possible or self.vision_change_possible or self.vision_loss_possible:
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


def _duration_category(signals: NormalizedSymptomSignals) -> str:
    if signals.transient_or_resolved_possible:
        return "transient_resolved"
    if signals.chronic_possible:
        return "years_chronic"
    if signals.gradual_possible:
        return "weeks_months"
    return "unknown"


def _severity(signals: NormalizedSymptomSignals, family: str) -> str:
    if family == "headache" and signals.severe_headache_possible:
        return "severe"
    if "有点" in signals.raw_text or "mild" in signals.raw_text.lower():
        return "mild"
    return "unknown"


def _evidence(signals: NormalizedSymptomSignals, keys: list[str]) -> str:
    phrases: list[str] = []
    for key in keys:
        phrases.extend(signals.matched_phrases.get(key, []))
    return "；".join(dict.fromkeys(phrases)) or signals.raw_text


def _evidence_phrases(signals: NormalizedSymptomSignals, keys: list[str]) -> list[str]:
    phrases: list[str] = []
    for key in keys:
        phrases.extend(signals.matched_phrases.get(key, []))
    return list(dict.fromkeys(phrases))


def _segment_for_evidence(text: str, evidence_phrases: list[str]) -> str:
    positions = [text.find(phrase) for phrase in evidence_phrases if phrase and phrase in text]
    if not positions:
        return text

    position = min(pos for pos in positions if pos >= 0)
    separators = ["，", ",", "；", ";", "。", ".", "但", "但是", "不过", "but"]
    start = 0
    end = len(text)
    for separator in separators:
        before = text.rfind(separator, 0, position)
        if before >= 0:
            start = max(start, before + len(separator))
        after = text.find(separator, position)
        if after >= 0:
            end = min(end, after)
    if end < len(text):
        tail = text[end:]
        next_piece_end = len(tail)
        for separator in separators:
            separator_pos = tail.find(separator, 1)
            if separator_pos >= 0:
                next_piece_end = min(next_piece_end, separator_pos)
        next_piece = tail[:next_piece_end]
        if _has_any(next_piece, TRANSIENT_OR_RESOLVED_PHRASES):
            end += next_piece_end
    return text[start:end].strip() or text


def _context_signals(signals: NormalizedSymptomSignals, evidence_keys: list[str]) -> NormalizedSymptomSignals:
    segment = _segment_for_evidence(signals.raw_text, _evidence_phrases(signals, evidence_keys))
    if segment == signals.raw_text:
        return signals
    return normalize_symptoms(segment)


def _observation_progression(
    signals: NormalizedSymptomSignals,
    context: NormalizedSymptomSignals,
) -> Progression:
    if context.transient_or_resolved_possible:
        return Progression.IMPROVING
    if context.stable_possible or signals.stable_possible:
        return Progression.STABLE
    if context.worsening_possible or signals.worsening_possible:
        return Progression.WORSENING
    return context.progression


def _associated_red_flags(signals: NormalizedSymptomSignals, family: str) -> list[str]:
    associated: list[str] = []
    if signals.weakness_possible and family != "weakness":
        associated.append("weakness")
    if signals.facial_asymmetry_possible and family != "facial_asymmetry":
        associated.append("facial_droop")
    if signals.speech_language_possible and family != "speech_language":
        associated.append("speech_language")
    if signals.confusion_awareness_possible and family != "confusion_awareness":
        associated.append("acute_confusion")
    if signals.sensory_possible and signals.laterality == Laterality.ONE_SIDE and family != "sensory":
        associated.append("focal_numbness")
    if signals.vision_loss_possible and family != "vision":
        associated.append("vision_loss")
    if signals.severe_headache_possible and family != "headache":
        associated.append("severe_headache")
    if signals.seizure_episode_possible and family != "seizure_episode":
        associated.append("seizure")
    if signals.loss_of_consciousness_possible and family != "loss_of_consciousness":
        associated.append("loss_of_consciousness")
    return associated


def _base_observation(
    signals: NormalizedSymptomSignals,
    family: str,
    strength: str,
    evidence_keys: list[str],
    *,
    severity: str | None = None,
    associated_red_flags: list[str] | None = None,
) -> NormalizedObservation:
    context = _context_signals(signals, evidence_keys)
    return NormalizedObservation(
        raw_text=signals.raw_text,
        symptom_family=family,
        signal_strength=strength,
        onset=context.onset.value,
        duration_category=_duration_category(context),
        laterality=context.laterality.value,
        progression=_observation_progression(signals, context).value,
        severity_qualifier=severity or _severity(signals, family),
        transient_or_resolved=context.transient_or_resolved_possible,
        associated_red_flags=associated_red_flags
        if associated_red_flags is not None
        else _associated_red_flags(signals, family),
        evidence_text=_evidence(signals, evidence_keys),
        source="deterministic",
        confidence=0.95 if strength == "true_red_flag" else 0.85,
    )


def observations_from_signals(signals: NormalizedSymptomSignals) -> list[NormalizedObservation]:
    """Build explicit observations from deterministic normalized signals."""
    observations: list[NormalizedObservation] = []

    if signals.weakness_possible:
        strength = "red_flag_candidate" if signals.laterality == Laterality.ONE_SIDE else "possible"
        if signals.onset == Onset.SUDDEN and signals.laterality == Laterality.ONE_SIDE:
            strength = "red_flag_candidate"
        observations.append(_base_observation(signals, "weakness", strength, ["weakness"]))

    if signals.facial_asymmetry_possible:
        observations.append(
            _base_observation(signals, "facial_asymmetry", "red_flag_candidate", ["facial_asymmetry"])
        )

    if signals.sensory_possible:
        strength = "possible"
        if signals.laterality == Laterality.ONE_SIDE:
            strength = "red_flag_candidate"
        if (
            signals.onset == Onset.SUDDEN
            and signals.laterality == Laterality.ONE_SIDE
            and signals.speech_language_possible
        ):
            strength = "true_red_flag"
        observations.append(_base_observation(signals, "sensory", strength, ["sensory"]))

    if signals.speech_language_possible:
        speech_flags: list[str] = []
        if signals.speech_slurring_possible:
            speech_flags.append("slurred_speech")
        if signals.word_finding_possible:
            speech_flags.append("word_finding_difficulty")
        observations.append(
            _base_observation(
                signals,
                "speech_language",
                "red_flag_candidate",
                ["speech_language", "speech_slur", "word_finding"],
                associated_red_flags=[*speech_flags, *_associated_red_flags(signals, "speech_language")],
            )
        )

    if signals.confusion_awareness_possible:
        observations.append(
            _base_observation(
                signals,
                "confusion_awareness",
                "red_flag_candidate",
                ["confusion_awareness"],
            )
        )

    if signals.memory_cognitive_possible:
        observations.append(
            _base_observation(signals, "memory_cognitive", "possible", ["memory_cognitive"])
        )

    if signals.gait_balance_possible:
        observations.append(_base_observation(signals, "gait_balance", "possible", ["gait_balance"]))

    if signals.headache_possible:
        strength = "true_red_flag" if signals.severe_headache_possible else "possible"
        associated = _associated_red_flags(signals, "headache")
        if strength == "possible" and associated:
            strength = "red_flag_candidate"
        observations.append(
            _base_observation(
                signals,
                "headache",
                strength,
                ["headache", "severe_headache"],
                severity="severe" if signals.severe_headache_possible else _severity(signals, "headache"),
                associated_red_flags=associated,
            )
        )

    if signals.vision_change_possible:
        observations.append(
            _base_observation(
                signals,
                "vision",
                "true_red_flag" if signals.vision_loss_possible else "possible",
                ["vision_change", "vision_loss"],
            )
        )

    if signals.seizure_episode_possible:
        observations.append(_base_observation(signals, "seizure_episode", "true_red_flag", ["seizure"]))

    if signals.loss_of_consciousness_possible:
        observations.append(
            _base_observation(
                signals,
                "loss_of_consciousness",
                "true_red_flag",
                ["loss_of_consciousness"],
            )
        )

    if signals.fall_head_injury_possible:
        fall_flags: list[str] = []
        if signals.fall_possible:
            fall_flags.append("fall")
        if signals.head_injury_possible:
            fall_flags.append("head_injury")
        observations.append(
            _base_observation(
                signals,
                "fall_head_injury",
                "red_flag_candidate" if signals.head_injury_possible else "possible",
                ["fall", "head_injury"],
                associated_red_flags=fall_flags,
            )
        )

    if signals.fatigue_possible and not signals.weakness_possible:
        observations.append(_base_observation(signals, "fatigue", "possible", ["fatigue"]))

    if not observations:
        observations.append(_base_observation(signals, "other", "possible", []))

    return observations


def normalize_observations(user_input: str) -> list[NormalizedObservation]:
    return observations_from_signals(normalize_symptoms(user_input))


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
        "severe_headache": _matches(text, SEVERE_HEADACHE_PHRASES),
        "vision_change": _matches(text, VISION_CHANGE_PHRASES),
        "vision_loss": _matches(text, VISION_LOSS_PHRASES),
        "seizure": _matches(text, SEIZURE_PHRASES),
        "loss_of_consciousness": _matches(text, LOSS_OF_CONSCIOUSNESS_PHRASES),
        "fall": _matches(text, FALL_PHRASES),
        "head_injury": _matches(text, HEAD_INJURY_PHRASES),
        "incontinence": _matches(text, INCONTINENCE_PHRASES),
        "tremor": _matches(text, TREMOR_PHRASES),
        "stiffness": _matches(text, STIFFNESS_PHRASES),
        "hallucination": _matches(text, HALLUCINATION_PHRASES),
        "personality": _matches(text, PERSONALITY_PHRASES),
        "transient_or_resolved": _matches(text, TRANSIENT_OR_RESOLVED_PHRASES),
        "fatigue": _matches(text, FATIGUE_PHRASES),
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
        severe_headache_possible=bool(matched["severe_headache"]),
        vision_change_possible=bool(matched["vision_change"]) or bool(matched["vision_loss"]),
        vision_loss_possible=bool(matched["vision_loss"]),
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
        transient_or_resolved_possible=bool(matched["transient_or_resolved"]),
        fatigue_possible=bool(matched["fatigue"]),
        non_neurological_expression_request=non_neuro_expression_request,
        matched_phrases={key: value for key, value in matched.items() if value},
    )
