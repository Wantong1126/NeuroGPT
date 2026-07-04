# SPDX-License-Identifier: MIT
"""Fine-grained elder observation extraction with an OpenAI-compatible backend."""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from core.llm import call_structured
from core.provider_settings import get_provider, get_provider_base_url, get_provider_model
from modules.elder_observation_response_renderer import render_elder_observation_response

SYSTEM_PROMPT = """
You are helping an elder-care status reporting system.
You are NOT diagnosing.
Your job is to extract the elder's concrete reported experience in detail.
Do not collapse the report into broad categories. Preserve the elder's raw wording.
Return valid JSON only.
Ask one best next question that would most help a caregiver understand what to check next.
The question must be specific to the elder's actual words.
The elder response must repeat the concrete issue, may give 2-4 plausible common
reasons when appropriate, must not diagnose, and must ask only one question.
Never use generic wording such as “这种情况可能有多种常见原因”.
Do not ask generic neuro questions unless the elder actually reports numbness, weakness,
speech change, face droop, confusion, fall, or acute severe headache.
For family summaries, avoid diagnosis and avoid alarming language.
All user-facing text must be concise Simplified Chinese.
""".strip()

SCHEMA = """
{
  "observations": [{
    "raw_quote": "老人原话",
    "domain": "sleep | pain | abdominal_digestive | mood | mobility | cognition | speech | appetite | digestion | breathing_chest | urinary | skin | medication | sensory | general",
    "specific_problem": "具体问题",
    "possible_reasons_plain": null,
    "why_this_matters": null,
    "body_location": null,
    "sensation_quality": null,
    "time_reference": null,
    "onset": null,
    "duration": null,
    "severity": null,
    "progression": null,
    "triggers_or_context": [],
    "associated_symptoms_reported": [],
    "associated_symptoms_denied": [],
    "functional_impact": null,
    "emotional_context": null,
    "elder_intent": null,
    "missing_information": [],
    "next_best_question": "一个贴合原话的问题",
    "staff_checklist": [],
    "family_safe_summary": "确认后可给家属看的非诊断总结",
    "red_flag_checks_needed": [],
    "confidence": "high | medium | low"
  }],
  "overall_plain_summary": "具体情况概括",
  "recommended_elder_response": "老人可读回应",
  "recommended_staff_handoff": "护理员交接",
  "recommended_family_summary_after_confirmation": "护理确认后家属总结"
}
"""

FORBIDDEN_NON_NEURO_QUESTION_TERMS = ("麻木", "没力", "动作不灵活", "感觉迟钝", "脸歪", "说话不清")


class ObservationDetail(BaseModel):
    raw_quote: str
    domain: str
    specific_problem: str
    possible_reasons_plain: str | None = None
    why_this_matters: str | None = None
    body_location: str | None = None
    sensation_quality: str | None = None
    time_reference: str | None = None
    onset: str | None = None
    duration: str | None = None
    severity: str | None = None
    progression: str | None = None
    triggers_or_context: list[str] = Field(default_factory=list)
    associated_symptoms_reported: list[str] = Field(default_factory=list)
    associated_symptoms_denied: list[str] = Field(default_factory=list)
    functional_impact: str | None = None
    emotional_context: str | None = None
    elder_intent: str | None = None
    missing_information: list[str] = Field(default_factory=list)
    next_best_question: str
    staff_checklist: list[str] = Field(default_factory=list)
    family_safe_summary: str
    red_flag_checks_needed: list[str] = Field(default_factory=list)
    confidence: str


class ObservationExtractionResult(BaseModel):
    observations: list[ObservationDetail]
    overall_plain_summary: str
    recommended_elder_response: str
    recommended_staff_handoff: str
    recommended_family_summary_after_confirmation: str


def extract_observation_details(raw_report: str) -> ObservationExtractionResult:
    """Extract concrete observations, falling back locally when DS is unavailable."""
    fallback = _heuristic_extraction(raw_report)
    if get_provider("observation_extractor_llm") != "openai_compatible":
        return fallback

    try:
        raw = call_structured(
            f"老人原话：{raw_report}",
            SYSTEM_PROMPT,
            SCHEMA,
            model=get_provider_model("observation_extractor_llm") or None,
            base_url=get_provider_base_url("observation_extractor_llm") or None,
            timeout_seconds=3.0,
            max_attempts=1,
        )
        result = ObservationExtractionResult.model_validate(raw)
        return _validate_result(result, raw_report, fallback)
    except Exception:
        return fallback


def _validate_result(
    result: ObservationExtractionResult,
    raw_report: str,
    fallback: ObservationExtractionResult,
) -> ObservationExtractionResult:
    if not result.observations:
        return fallback
    for observation in result.observations:
        if not observation.raw_quote:
            observation.raw_quote = raw_report
        if not observation.specific_problem or not observation.next_best_question:
            return fallback
        neuro_question_allowed = (
            observation.domain in {"sensory", "speech", "cognition", "mobility"}
            or observation.body_location == "头部"
            or "头痛" in observation.specific_problem
        )
        if not neuro_question_allowed:
            if any(term in observation.next_best_question for term in FORBIDDEN_NON_NEURO_QUESTION_TERMS):
                return fallback
    # The model extracts detail, but local rendering owns the elder-facing wording.
    # This prevents a structurally valid response from reintroducing generic copy.
    result.recommended_elder_response = format_observation_elder_response(result.observations[0])
    if not result.recommended_staff_handoff:
        result.recommended_staff_handoff = fallback.recommended_staff_handoff
    if not result.recommended_family_summary_after_confirmation:
        result.recommended_family_summary_after_confirmation = fallback.recommended_family_summary_after_confirmation
    return result


def _heuristic_extraction(raw_report: str) -> ObservationExtractionResult:
    text = (raw_report or "").strip()
    if _is_abdominal_report(text):
        detail = ObservationDetail(
            raw_quote=text,
            domain="abdominal_digestive",
            specific_problem="腹部不适/腹痛",
            body_location=_abdominal_location(text),
            sensation_quality=_abdominal_quality(text),
            time_reference=_abdominal_time_reference(text),
            onset="突然" if "突然" in text else None,
            duration=_duration_from_text(text),
            severity=_severity_from_text(text),
            missing_information=["腹部具体位置", "不舒服的感觉", "持续多久", "是否加重", "是否伴随其他不适"],
            next_best_question="肚子具体哪个位置最痛？是上腹、肚脐周围、下腹，还是左右某一边？",
            staff_checklist=["查看腹部不适位置和程度", "确认持续时间及是否加重", "询问进食、排便及伴随不适"],
            family_safe_summary="老人反映腹部不适，护理员将尽快确认具体位置、持续时间和伴随情况。",
            red_flag_checks_needed=[
                "持续加重或剧烈腹痛", "发热", "呕吐", "腹泻", "黑便/血便",
                "胸闷/胸痛/气短/出汗", "晕厥", "近期跌倒或外伤", "腹部明显变硬", "无法进食/喝水",
            ],
            confidence="fallback",
        )
        return _result_from_detail(detail)

    if _has_any(text, ("睡不好", "睡不着", "没睡好", "醒很多次", "半夜醒")):
        detail = ObservationDetail(
            raw_quote=text,
            domain="sleep",
            specific_problem="昨晚睡眠质量不好" if "昨晚" in text else "睡眠质量不好",
            time_reference="昨晚" if "昨晚" in text else None,
            missing_information=[
                "是入睡困难、半夜醒来、早醒，还是睡得浅",
                "是否因为疼痛、起夜、心慌、焦虑或环境影响",
                "今天白天精神是否受影响",
            ],
            next_best_question="昨晚是睡不着，还是半夜醒了很多次？",
            staff_checklist=["了解具体睡眠困难类型", "询问夜间疼痛、起夜、心慌或情绪影响", "观察白天精神状态"],
            family_safe_summary="老人反映昨晚睡眠不好，护理员将进一步了解原因和白天精神状态。",
            red_flag_checks_needed=["明显胸闷或心慌", "白天意识或精神状态明显改变"],
            confidence="fallback",
        )
        return _result_from_detail(detail)

    if _is_shoulder_back_soreness(text):
        location = _musculoskeletal_location(text)
        quality = _musculoskeletal_quality(text)
        problem_quality = "酸痛" if quality == "酸" else quality
        time_reference = _musculoskeletal_time_reference(text)
        next_question = (
            "今天有没有摔倒、扭到，或者疼痛是突然一下子很重？"
            if time_reference and quality in {"痛", "刺痛", "抽着痛"}
            else "这种酸痛是今天刚出现，还是已经有几天了？"
        )
        detail = ObservationDetail(
            raw_quote=text,
            domain="pain",
            specific_problem=f"{location}{problem_quality}",
            body_location=location,
            sensation_quality=quality,
            time_reference=time_reference,
            onset=time_reference,
            missing_information=[
                "是今天刚出现还是持续几天",
                "是否摔倒、扭伤、搬重物、活动后加重",
                "是否影响站立、走路、翻身、吃饭",
                "是否伴随胸闷、气短、出汗、发热、麻木、无力",
            ],
            next_best_question=next_question,
            staff_checklist=[
                "是否摔倒、扭伤、搬重物、活动后加重",
                "疼痛部位：上背/下背/腰/肩颈/一侧",
                "疼痛性质：酸、胀、刺痛、抽痛、僵硬",
                "是否影响站立/走路/翻身/吃饭",
                "是否伴随胸闷/气短/出汗/发热/麻木/无力",
                "是否持续加重",
            ],
            family_safe_summary=f"老人反映{location}{quality}，护理员将确认持续时间、活动影响及是否加重。",
            red_flag_checks_needed=["摔倒或扭伤", "胸闷", "气短", "出汗", "发热", "麻木", "无力", "疼痛持续加重"],
            confidence="fallback",
        )
        return _result_from_detail(detail)

    if _has_any(text, ("手麻", "手发麻", "手麻木")):
        detail = ObservationDetail(
            raw_quote=text,
            domain="sensory",
            specific_problem="手部发麻",
            body_location="手部",
            sensation_quality="麻",
            missing_information=["哪只手", "是突然出现还是逐渐出现", "是否伴随没力、说话不清、脸歪、走路不稳"],
            next_best_question="请告诉我是哪只手麻、是不是突然出现，以及有没有同时没力、说话不清、脸歪或走路不稳？",
            staff_checklist=["确认左右侧", "确认开始时间", "检查握力、说话、面部和行走变化"],
            family_safe_summary="老人反映手部发麻，护理员将确认左右侧、开始时间及是否伴随其他变化。",
            red_flag_checks_needed=["单侧明显没力", "说话不清", "脸歪", "走路不稳"],
            confidence="fallback",
        )
        return _result_from_detail(detail)

    if _has_any(text, ("头痛", "头疼", "头很痛", "头突然疼", "头突然很痛")):
        detail = ObservationDetail(
            raw_quote=text,
            domain="pain",
            specific_problem="头部疼痛",
            body_location="头部",
            sensation_quality="痛",
            time_reference="突然" if "突然" in text else None,
            missing_information=["是突然很严重还是慢慢开始", "是否伴随呕吐、看不清、说话不清或手脚没力"],
            next_best_question="头痛是突然一下子很严重，还是慢慢开始的，有没有呕吐、看不清、说话不清或手脚没力？",
            staff_checklist=["确认头痛开始方式和严重程度", "询问呕吐、视力、说话和手脚力量变化"],
            family_safe_summary="老人反映头痛，护理员将确认开始方式、严重程度和是否伴随其他不适。",
            red_flag_checks_needed=["突然剧烈头痛", "呕吐", "看不清", "说话不清", "手脚没力"],
            confidence="fallback",
        )
        return _result_from_detail(detail)

    if _has_any(text, ("不想麻烦孩子", "不想麻烦家人", "孤单", "没意思", "心情不好")):
        intent = "不想麻烦孩子" if "不想麻烦孩子" in text else "表达心情或孤单感受"
        detail = ObservationDetail(
            raw_quote=text,
            domain="mood",
            specific_problem="不想麻烦家人或近期情绪低落",
            emotional_context=text,
            elder_intent=intent,
            missing_information=["是否有身体不舒服但不愿麻烦家人", "最近是否心情不好或更想独处", "是否需要护理员陪伴或联系家人"],
            next_best_question="您是哪里不舒服，还是最近心情不好、想一个人待着？",
            staff_checklist=["主动询问身体不适", "了解情绪和陪伴需要", "确认是否需要联系家属"],
            family_safe_summary="老人表达了不想麻烦家人或近期心情方面的顾虑，护理员会先了解其身体和情绪需要。",
            red_flag_checks_needed=["明显绝望", "伤害自己的想法", "拒绝进食或长期不愿交流"],
            confidence="fallback",
        )
        return _result_from_detail(detail)

    detail = ObservationDetail(
        raw_quote=text,
        domain="general",
        specific_problem=text or "老人表示不舒服",
        missing_information=["具体哪里不舒服", "什么时候开始", "是否正在加重", "是否影响日常活动"],
        next_best_question="您最不舒服的是哪里？这种感觉是什么时候开始的，现在有没有越来越重？",
        staff_checklist=["确认具体不适部位和感觉", "确认开始时间和变化", "观察是否影响活动"],
        family_safe_summary=f"老人反映“{text}”，护理员将进一步确认具体情况。",
        red_flag_checks_needed=["突然明显加重", "意识、说话、呼吸或行动突然变化"],
        confidence="fallback",
    )
    return _result_from_detail(detail)


def _result_from_detail(detail: ObservationDetail) -> ObservationExtractionResult:
    return ObservationExtractionResult(
        observations=[detail],
        overall_plain_summary=detail.specific_problem,
        recommended_elder_response=format_observation_elder_response(detail),
        recommended_staff_handoff=(
            f"老人原话：{detail.raw_quote}。具体情况：{detail.specific_problem}。"
            f"请重点确认：{'；'.join(detail.staff_checklist)}。"
        ),
        recommended_family_summary_after_confirmation=detail.family_safe_summary,
    )


def format_observation_elder_response(
    detail: ObservationDetail,
    question: str | None = None,
    *,
    include_question: bool = True,
    max_chars: int | None = 220,
) -> str:
    """Compatibility wrapper around the unified accumulated-observation renderer."""
    response = render_elder_observation_response(
        detail.model_dump(mode="json"),
        detail.raw_quote,
        question or detail.next_best_question if include_question else None,
        response_mode="initial" if include_question else "complete",
    )
    if max_chars is not None and len(response) > max_chars:
        return response[:max_chars]
    return response


def _is_shoulder_back_soreness(text: str) -> bool:
    has_location = _has_any(text, ("肩膀", "肩", "背", "腰", "脖子", "颈", "胳膊", "腿", "关节", "肌肉"))
    return has_location and _has_any(text, ("酸", "酸痛", "疼", "痛", "僵", "僵硬"))


def _musculoskeletal_location(text: str) -> str:
    if _has_any(text, ("肩膀", "肩")) and "背" in text:
        return "肩膀和背部"
    for terms, normalized in (
        (("上背",), "上背"),
        (("下背",), "下背"),
        (("背",), "背部"),
        (("腰",), "腰部"),
        (("脖子", "颈"), "肩颈"),
        (("肩膀", "肩"), "肩膀"),
        (("胳膊",), "胳膊"),
        (("腿",), "腿部"),
        (("关节",), "关节"),
        (("肌肉",), "肌肉"),
    ):
        if any(term in text for term in terms):
            return normalized
    return "身体"


def _musculoskeletal_quality(text: str) -> str:
    for terms, normalized in (
        (("刺痛",), "刺痛"),
        (("抽着痛", "抽痛"), "抽着痛"),
        (("僵硬", "僵"), "僵硬"),
        (("酸",), "酸"),
        (("胀",), "胀"),
        (("痛", "疼"), "痛"),
    ):
        if any(term in text for term in terms):
            return normalized
    return "不舒服"


def _musculoskeletal_time_reference(text: str) -> str | None:
    if "今天早上" in text or "今早" in text:
        return "今天早上"
    if "早上" in text:
        return "早上"
    if "今天刚出现" in text or "今天开始" in text:
        return "今天刚出现"
    return None


def _is_abdominal_report(text: str) -> bool:
    return _has_any(text, ("肚子痛", "肚子疼", "腹痛", "胃痛", "上腹痛", "下腹痛", "肚子胀", "胃胀", "恶心", "拉肚子")) or (
        _has_any(text, ("肚子", "腹", "胃")) and _has_any(text, ("痛", "疼", "胀"))
    )


def _abdominal_location(text: str) -> str | None:
    for term in ("上腹", "肚脐周围", "下腹", "左侧腹部", "右侧腹部"):
        if term in text:
            return term
    return None


def _abdominal_quality(text: str) -> str | None:
    # A bare complaint of pain still needs the pain/pressure/burning distinction.
    qualities = []
    for normalized, terms in (
        ("绞着痛", ("绞着痛", "绞痛")),
        ("烧心", ("烧心",)),
        ("胀", ("胀",)),
        ("恶心想吐", ("恶心", "想吐")),
    ):
        if any(term in text for term in terms):
            qualities.append(normalized)
    if qualities and "绞着痛" not in qualities and _has_any(text, ("痛", "疼")):
        qualities.insert(0, "痛")
    return "、".join(qualities) or None


def _abdominal_time_reference(text: str) -> str | None:
    if "今天早上" in text or "今早" in text:
        return "今天早上"
    if "早上" in text:
        return "早上"
    if "刚刚" in text or "刚才" in text:
        return "刚刚"
    return None


def _duration_from_text(text: str) -> str | None:
    match = re.search(r"(?:刚刚开始|刚才开始|\d+[个]?(?:分钟|小时|天)|[一两半]+(?:小时|天|早上))", text)
    return match.group(0) if match else None


def _severity_from_text(text: str) -> str | None:
    for term in ("非常痛", "特别痛", "剧烈", "很痛", "能忍", "还好"):
        if term in text:
            return term
    return None


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)
