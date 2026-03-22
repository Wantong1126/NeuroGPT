# SPDX-License-Identifier: MIT
"""
NeuroGPT v2 — Step 2: Symptom Extractor
Uses LLM to parse free-text user input into ExtractedSymptoms.
Replace with real LLM call once API key is configured.
"""
from __future__ import annotations
from core.models import ExtractedSymptoms, Onset, Laterality, Progression, RedFlags
from core.config_loader import load_prompt_template
from core.llm import call_structured, call

SYSTEM_PROMPT = (
    "You are a clinical symptom-extraction assistant for a medical education tool "
    "targeting older adults and their caregivers. Your task is to accurately parse "
    "free-form symptom descriptions into a structured clinical profile. "
    "Be conservative: when uncertain, mark fields as UNKNOWN rather than guessing. "
    "Do not make diagnostic conclusions — only extract symptoms as described."
)

SCHEMA = """
{
  "symptom_type": ["list of categories: motor/cognitive/speech/behavioral/sensory/gait/other"],
  "primary_symptom": "main complaint in user's own words",
  "onset": "sudden | gradual | chronic | unknown",
  "laterality": "one_side | both_sides | central | unknown",
  "duration_text": "how long symptoms have been present",
  "progression": "first_time | worsening | stable | improving | recurring | unknown",
  "frequency_text": "intermittent / constant / single episode",
  "red_flags": {
    "weakness_one_side": true/false,
    "facial_droop": true/false,
    "slurred_speech": true/false,
    "sudden_onset": true/false,
    "acute_confusion": true/false,
    "seizure": true/false,
    "loss_of_consciousness": true/false,
    "severe_headache": true/false,
    "vision_loss": true/false,
    "gait_imbalance": true/false,
    "focal_numbness": true/false,
    "new_falls": true/false,
    "head_injury": true/false,
    "incontinence": true/false,
    "stroke_beFAST": true/false
  },
  "memory_concern": true/false,
  "word_finding_difficulty": true/false,
  "disorientation": true/false,
  "tremor_present": true/false,
  "falls_present": true/false,
  "gait_difficulty": true/false,
  "stiffness": true/false,
  "sleep_disturbance": true/false,
  "apathy": true/false,
  "hallucinations": true/false,
  "personality_change": true/false,
  "denial_detected": true/false,
  "fear_detected": true/false,
  "delay_reason": "why user may be delaying, if expressed"
}
"""

def extract_symptoms(user_input: str) -> ExtractedSymptoms:
    """
    Main entry point. Calls LLM to extract structured symptoms.
    Falls back to a heuristic extractor if LLM is not configured.
    """
    template = load_prompt_template("symptom_extractor")
    if not template:
        template = (
            "Extract clinical features from this symptom description. "
            "User says: {user_input}"
        )
    user_prompt = template.format(user_input=user_input)

    try:
        raw = call_structured(user_prompt, SYSTEM_PROMPT, SCHEMA)
    except RuntimeError as e:
        # LLM not configured — use heuristic fallback
        return _heuristic_extract(user_input)

    return _parse_extracted(raw, user_input)


def _parse_extracted(raw: dict, user_input: str) -> ExtractedSymptoms:
    """Parse LLM JSON output into Pydantic model."""
    rf_data = raw.get("red_flags", {})

    def _bool(val) -> bool:
        return bool(val) if val is not None else False

    rf = RedFlags(
        weakness_one_side=_bool(rf_data.get("weakness_one_side")),
        facial_droop=_bool(rf_data.get("facial_droop")),
        slurred_speech=_bool(rf_data.get("slurred_speech")),
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
        stroke_beFAST=_bool(rf_data.get("stroke_beFAST")),
    )

    onset_map = {
        "sudden": Onset.SUDDEN, "gradual": Onset.GRADUAL,
        "chronic": Onset.CHRONIC, "unknown": Onset.UNKNOWN,
    }
    lat_map = {
        "one_side": Laterality.ONE_SIDE,
        "both_sides": Laterality.BOTH_SIDES,
        "central": Laterality.CENTRAL, "unknown": Laterality.UNKNOWN,
    }
    prog_map = {
        "first_time": Progression.FIRST_TIME, "worsening": Progression.WORSENING,
        "stable": Progression.STABLE, "improving": Progression.IMPROVING,
        "recurring": Progression.RECURRING, "unknown": Progression.UNKNOWN,
    }

    return ExtractedSymptoms(
        raw_input=user_input,
        symptom_type=raw.get("symptom_type", []),
        primary_symptom=raw.get("primary_symptom", user_input),
        onset=onset_map.get(raw.get("onset", "unknown"), Onset.UNKNOWN),
        laterality=lat_map.get(raw.get("laterality", "unknown"), Laterality.UNKNOWN),
        duration_text=raw.get("duration_text", ""),
        progression=prog_map.get(raw.get("progression", "unknown"), Progression.UNKNOWN),
        frequency_text=raw.get("frequency_text", ""),
        red_flags=rf,
        memory_concern=_bool(raw.get("memory_concern")),
        word_finding_difficulty=_bool(raw.get("word_finding_difficulty")),
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


def _heuristic_extract(user_input: str) -> ExtractedSymptoms:
    """
    Fallback when LLM is not configured.
    Performs simple keyword matching to produce a best-effort ExtractedSymptoms.
    NOT clinically accurate — always prefer real LLM call.
    """
    text = user_input.lower()

    keywords_sudden = ["突然", "sudden", "一下子", "一下子", "刚才", "刚刚"]
    keywords_one_side = ["一边", "一侧", "one side", "left", "right", "单侧"]
    keywords_high_risk = [
        "无力", "weak", "speech", "含糊", "嘴角下垂", "facial droop",
        "面瘫", "口齿不清", "叫不醒", "unconscious", "seizure", "抽搐",
        "倒地", "失去意识", "剧烈头痛", "thunderclap headache",
    ]
    keywords_gait = ["走路", "步态", "gait", "平衡", "平衡", "走路不稳", "跌倒", "摔倒"]
    keywords_cognitive = ["记性", "memory", "认知", "不认识人", "叫不出名字", "糊涂", "confusion", "呆"]

    onset = Onset.SUDDEN if any(k in text for k in keywords_sudden) else Onset.UNKNOWN
    laterality = Laterality.ONE_SIDE if any(k in text for k in keywords_one_side) else Laterality.UNKNOWN

    rf = RedFlags(
        weakness_one_side=any(k in text for k in ["无力", "weak", "动不了"]),
        slurred_speech=any(k in text for k in ["含糊", "口齿不清", "说不清"]),
        sudden_onset=any(k in text for k in keywords_sudden),
        acute_confusion=any(k in text for k in ["糊涂", "confusion", "不认识人", "神志不清"]),
        seizure=any(k in text for k in ["抽搐", "seizure", "倒地"]),
        severe_headache=any(k in text for k in ["剧烈头痛", "爆裂样头痛"]),
        gait_imbalance=any(k in text for k in keywords_gait),
        gait_difficulty=any(k in text for k in keywords_gait),
        falls_present=any(k in text for k in ["跌倒", "摔倒", "摔跤"]),
        memory_concern=any(k in text for k in keywords_cognitive),
    )

    return ExtractedSymptoms(
        raw_input=user_input,
        primary_symptom=user_input[:50],
        onset=onset,
        laterality=laterality,
        progression=Progression.UNKNOWN,
        red_flags=rf,
    )
