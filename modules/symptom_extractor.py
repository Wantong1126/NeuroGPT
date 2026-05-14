# SPDX-License-Identifier: MIT
"""
NeuroGPT v2 - Step 2: Symptom Extractor.
Uses a provider-selected extractor and falls back to heuristics.
"""
from __future__ import annotations

from core.models import ExtractedSymptoms, Onset, Laterality, Progression, RedFlags
from core.config_loader import load_prompt_template
from core.llm import call_structured
from core.provider_settings import get_provider

SYSTEM_PROMPT = (
    "You are a clinical symptom-extraction assistant for a medical education tool "
    "targeting older adults and their caregivers. Your task is to parse free-form "
    "symptom descriptions into a structured clinical profile. "
    "Be conservative: when uncertain, mark fields as unknown rather than guessing."
)

SCHEMA = """
{
  "symptom_type": ["motor", "cognitive", "speech", "behavioral", "sensory", "gait", "other"],
  "primary_symptom": "main complaint in the user's own words",
  "onset": "sudden | gradual | chronic | unknown",
  "laterality": "one_side | both_sides | central | unknown",
  "duration_text": "how long symptoms have been present",
  "progression": "first_time | worsening | stable | improving | recurring | unknown",
  "frequency_text": "intermittent / constant / single episode",
  "red_flags": {
    "weakness_one_side": true,
    "facial_droop": false,
    "slurred_speech": false,
    "sudden_onset": true,
    "acute_confusion": false,
    "seizure": false,
    "loss_of_consciousness": false,
    "severe_headache": false,
    "vision_loss": false,
    "gait_imbalance": false,
    "focal_numbness": false,
    "new_falls": false,
    "head_injury": false,
    "incontinence": false,
    "stroke_beFAST": false
  }
}
"""


SPEECH_ONSET_UNKNOWN_CLARIFICATION_PATTERNS = [
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

CLINICAL_SPEECH_MARKERS = [
    "讲话不清",
    "说话不清",
    "口齿不清",
    "含糊",
    "说不出话",
    "不会说话",
    "表达困难",
    "找词困难",
    "叫不出名字",
    "说话慢",
    "slurred",
    "trouble speaking",
    "can't speak",
    "cannot speak",
    "cannot get words out",
    "can't get words out",
    "word finding",
    "word-finding",
    "aphasia",
]


def _is_non_neurological_expression_request(text: str) -> bool:
    lowered = text.lower()
    if not _has_any(lowered, SPEECH_ONSET_UNKNOWN_CLARIFICATION_PATTERNS):
        return False
    return not _has_any(lowered, CLINICAL_SPEECH_MARKERS)


def _clean_symptom_types(symptom_types: list[str], remove_speech: bool = False) -> list[str]:
    cleaned = [item for item in symptom_types if item != "speech"] if remove_speech else list(symptom_types)
    return cleaned or ["other"]



def extract_symptoms(user_input: str) -> ExtractedSymptoms:
    """Main entry point."""
    provider = get_provider("symptom_extractor")
    if provider != "openai_compatible":
        return _heuristic_extract(user_input)

    template = load_prompt_template("symptom_extractor") or "Extract clinical features from: {user_input}"
    user_prompt = template.format(user_input=user_input)

    try:
        raw = call_structured(user_prompt, SYSTEM_PROMPT, SCHEMA)
    except Exception:
        return _heuristic_extract(user_input)

    return _parse_extracted(raw, user_input)



def _parse_extracted(raw: dict, user_input: str) -> ExtractedSymptoms:
    """Parse LLM JSON output into Pydantic model."""
    rf_data = raw.get("red_flags", {})
    is_expression_request = _is_non_neurological_expression_request(user_input)

    def _bool(value) -> bool:
        return bool(value) if value is not None else False

    onset_map = {
        "sudden": Onset.SUDDEN,
        "gradual": Onset.GRADUAL,
        "chronic": Onset.CHRONIC,
        "unknown": Onset.UNKNOWN,
    }
    laterality_map = {
        "one_side": Laterality.ONE_SIDE,
        "both_sides": Laterality.BOTH_SIDES,
        "central": Laterality.CENTRAL,
        "unknown": Laterality.UNKNOWN,
    }
    progression_map = {
        "first_time": Progression.FIRST_TIME,
        "worsening": Progression.WORSENING,
        "stable": Progression.STABLE,
        "improving": Progression.IMPROVING,
        "recurring": Progression.RECURRING,
        "unknown": Progression.UNKNOWN,
    }

    symptom_type = raw.get("symptom_type", [])
    if is_expression_request:
        symptom_type = _clean_symptom_types(symptom_type, remove_speech=True)

    return ExtractedSymptoms(
        raw_input=user_input,
        symptom_type=symptom_type,
        primary_symptom=raw.get("primary_symptom", user_input),
        onset=onset_map.get(raw.get("onset", "unknown"), Onset.UNKNOWN),
        laterality=laterality_map.get(raw.get("laterality", "unknown"), Laterality.UNKNOWN),
        duration_text=raw.get("duration_text", ""),
        progression=progression_map.get(raw.get("progression", "unknown"), Progression.UNKNOWN),
        frequency_text=raw.get("frequency_text", ""),
        red_flags=RedFlags(
            weakness_one_side=_bool(rf_data.get("weakness_one_side")),
            facial_droop=_bool(rf_data.get("facial_droop")),
            slurred_speech=False if is_expression_request else _bool(rf_data.get("slurred_speech")),
            sudden_onset=_bool(rf_data.get("sudden_onset")),
            acute_confusion=_bool(rf_data.get("acute_confusion")),
            seizure=_bool(rf_data.get("seizure")),
            loss_of_consciousness=_bool(rf_data.get("loss_of_consciousness")),
            severe_headache=_bool(rf_data.get("severe_headache")),
            vision_loss=_bool(rf_data.get("vision_loss")),
            gait_imbalance=_bool(rf_data.get("gait_imbalance")),
            focal_numbness=_bool(rf_data.get("focal_numbness")),
            new_falls=_bool(rf_data.get("new_falls")),
            head_injury=_bool(rf_data.get("head_injury")),
            incontinence=_bool(rf_data.get("incontinence")),
            stroke_beFAST=False if is_expression_request else _bool(rf_data.get("stroke_beFAST")),
        ),
        memory_concern=_bool(raw.get("memory_concern")),
        word_finding_difficulty=False if is_expression_request else _bool(raw.get("word_finding_difficulty")),
        disorientation=_bool(raw.get("disorientation")),
        tremor_present=_bool(raw.get("tremor_present")),
        falls_present=_bool(raw.get("falls_present")),
        gait_difficulty=_bool(raw.get("gait_difficulty")),
        stiffness=_bool(raw.get("stiffness")),
        sleep_disturbance=_bool(raw.get("sleep_disturbance")),
        apathy=_bool(raw.get("apathy")),
        hallucinations=_bool(raw.get("hallucinations")),
        personality_change=_bool(raw.get("personality_change")),
        denial_detected=_bool(raw.get("denial_detected")),
        fear_detected=_bool(raw.get("fear_detected")),
        delay_reason=raw.get("delay_reason", ""),
        llm_raw_json=str(raw),
    )



def _has_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)



def _heuristic_extract(user_input: str) -> ExtractedSymptoms:
    """Best-effort parser used when LLM access is unavailable."""
    text = user_input.lower()
    is_expression_request = _is_non_neurological_expression_request(text)

    sudden_keywords = ["突然", "忽然", "一下子", "今早", "今天早上", "today", "this morning", "sudden", "suddenly"]
    gradual_keywords = ["慢慢", "逐渐", "越来越", "几个月", "几周", "gradual", "slowly"]
    chronic_keywords = ["几年", "多年", "长期", "一直", "for years", "years", "longstanding", "chronic"]
    one_side_keywords = ["左", "右", "左边", "右边", "单侧", "一侧", "one side", "left", "right"]
    both_sides_keywords = ["双侧", "两边", "both sides", "bilateral"]
    worsening_keywords = ["加重", "恶化", "越来越", "更严重", "worsening", "getting worse"]

    weakness_keywords = ["无力", "没力", "抬不起来", "动不了", "weak", "weakness", "cannot move", "can't move"]
    speech_keywords = [
        "讲话不清",
        "说话不清",
        "口齿不清",
        "含糊",
        "说不清",
        "slurred",
        "speech is unclear",
    ]
    speech_language_keywords = [
        *speech_keywords,
        "表达困难",
        "表达有点困难",
        "说不出话",
        "不会说话",
        "说话慢",
        "说话越来越慢",
        "trouble speaking",
        "trouble expressing",
        "cannot get words out",
        "can't get words out",
        "cannot speak",
        "can't speak",
        "aphasia",
    ]
    facial_keywords = ["嘴歪", "面瘫", "脸歪", "facial droop", "face droop", "droopy", "drooping"]
    confusion_keywords = ["糊涂", "混乱", "不认人", "confusion", "disoriented"]
    seizure_keywords = ["抽搐", "癫痫", "seizure", "convulsion"]
    loc_keywords = ["昏迷", "失去意识", "晕倒", "unconscious", "passed out"]
    headache_keywords = ["剧烈头痛", "爆炸样头痛", "thunderclap", "severe headache"]
    vision_keywords = ["看不见", "视力下降", "vision loss", "blind"]
    numbness_keywords = ["发麻", "麻木", "numb", "numbness"]
    gait_keywords = ["走路不稳", "步态", "平衡差", "gait", "imbalance"]
    fall_keywords = ["跌倒", "摔倒", "falls", "fall"]
    injury_keywords = ["撞到头", "头部受伤", "head injury"]
    incontinence_keywords = ["失禁", "大小便失禁", "incontinence"]
    memory_keywords = ["记忆", "忘事", "记不住", "memory"]
    word_finding_keywords = [
        "找词困难",
        "叫不出名字",
        "表达困难",
        "表达有点困难",
        "说不出话",
        "不会说话",
        "word finding",
        "word-finding",
        "cannot get words out",
        "can't get words out",
    ]
    tremor_keywords = ["手抖", "震颤", "tremor"]
    stiffness_keywords = ["僵硬", "stiffness"]
    hallucination_keywords = ["幻觉", "看到不存在", "hallucination"]
    personality_keywords = ["性格改变", "脾气变", "personality change"]

    if _has_any(text, sudden_keywords):
        onset = Onset.SUDDEN
    elif _has_any(text, chronic_keywords):
        onset = Onset.CHRONIC
    elif _has_any(text, gradual_keywords):
        onset = Onset.GRADUAL
    else:
        onset = Onset.UNKNOWN

    if _has_any(text, both_sides_keywords):
        laterality = Laterality.BOTH_SIDES
    elif _has_any(text, one_side_keywords):
        laterality = Laterality.ONE_SIDE
    else:
        laterality = Laterality.UNKNOWN

    if _has_any(text, worsening_keywords):
        progression = Progression.WORSENING
    elif onset != Onset.UNKNOWN:
        progression = Progression.FIRST_TIME
    else:
        progression = Progression.UNKNOWN

    weakness_one_side = _has_any(text, weakness_keywords) and laterality == Laterality.ONE_SIDE
    facial_droop = _has_any(text, facial_keywords)
    slurred_speech = False if is_expression_request else _has_any(text, speech_keywords)
    word_finding_difficulty = False if is_expression_request else _has_any(text, word_finding_keywords)
    speech_language_symptom = False if is_expression_request else _has_any(text, speech_language_keywords)
    acute_confusion = _has_any(text, confusion_keywords)
    seizure = _has_any(text, seizure_keywords)
    loss_of_consciousness = _has_any(text, loc_keywords)
    severe_headache = _has_any(text, headache_keywords)
    vision_loss = _has_any(text, vision_keywords)
    focal_numbness = _has_any(text, numbness_keywords) and laterality == Laterality.ONE_SIDE
    gait_imbalance = _has_any(text, gait_keywords)
    new_falls = _has_any(text, fall_keywords)
    head_injury = _has_any(text, injury_keywords)
    incontinence = _has_any(text, incontinence_keywords)

    stroke_fast = weakness_one_side or facial_droop or (slurred_speech and onset == Onset.SUDDEN)

    symptom_types: list[str] = []
    if weakness_one_side or gait_imbalance or _has_any(text, tremor_keywords):
        symptom_types.append("motor")
    if speech_language_symptom or word_finding_difficulty:
        symptom_types.append("speech")
    if acute_confusion or _has_any(text, memory_keywords):
        symptom_types.append("cognitive")
    if not symptom_types:
        symptom_types.append("other")

    return ExtractedSymptoms(
        raw_input=user_input,
        symptom_type=_clean_symptom_types(symptom_types, remove_speech=is_expression_request),
        primary_symptom=user_input[:80],
        onset=onset,
        laterality=laterality,
        progression=progression,
        red_flags=RedFlags(
            weakness_one_side=weakness_one_side,
            facial_droop=facial_droop,
            slurred_speech=slurred_speech,
            sudden_onset=onset == Onset.SUDDEN,
            acute_confusion=acute_confusion,
            seizure=seizure,
            loss_of_consciousness=loss_of_consciousness,
            severe_headache=severe_headache,
            vision_loss=vision_loss,
            gait_imbalance=gait_imbalance,
            focal_numbness=focal_numbness,
            new_falls=new_falls,
            head_injury=head_injury,
            incontinence=incontinence,
            stroke_beFAST=stroke_fast,
        ),
        memory_concern=_has_any(text, memory_keywords),
        word_finding_difficulty=word_finding_difficulty,
        disorientation=acute_confusion,
        tremor_present=_has_any(text, tremor_keywords),
        falls_present=new_falls,
        gait_difficulty=gait_imbalance,
        stiffness=_has_any(text, stiffness_keywords),
        hallucinations=_has_any(text, hallucination_keywords),
        personality_change=_has_any(text, personality_keywords),
    )
