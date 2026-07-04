# SPDX-License-Identifier: MIT
"""Fine-grained elder observation extraction with an OpenAI-compatible backend."""
from __future__ import annotations

from pydantic import BaseModel, Field

from core.llm import call_structured
from core.provider_settings import get_provider, get_provider_base_url, get_provider_model

SYSTEM_PROMPT = """
You are helping an elder-care status reporting system.
You are NOT diagnosing.
Your job is to extract the elder's concrete reported experience in detail.
Do not collapse the report into broad categories. Preserve the elder's raw wording.
Return valid JSON only.
Ask one best next question that would most help a caregiver understand what to check next.
The question must be specific to the elder's actual words.
Do not ask generic neuro questions unless the elder actually reports numbness, weakness,
speech change, face droop, confusion, fall, or acute severe headache.
For family summaries, avoid diagnosis and avoid alarming language.
All user-facing text must be concise Simplified Chinese.
""".strip()

SCHEMA = """
{
  "observations": [{
    "raw_quote": "老人原话",
    "domain": "sleep | pain | mood | mobility | cognition | speech | appetite | digestion | breathing_chest | urinary | skin | medication | sensory | general",
    "specific_problem": "具体问题",
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
    primary = result.observations[0]
    if (
        not result.recommended_elder_response
        or primary.raw_quote not in result.recommended_elder_response
        or primary.next_best_question not in result.recommended_elder_response
    ):
        result.recommended_elder_response = _format_elder_response(result.observations[0])
    if not result.recommended_staff_handoff:
        result.recommended_staff_handoff = fallback.recommended_staff_handoff
    if not result.recommended_family_summary_after_confirmation:
        result.recommended_family_summary_after_confirmation = fallback.recommended_family_summary_after_confirmation
    return result


def _heuristic_extraction(raw_report: str) -> ObservationExtractionResult:
    text = (raw_report or "").strip()
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
            next_best_question="昨晚是睡不着，还是半夜醒了很多次？有没有因为疼、心慌、起夜，或者心里有事睡不着？",
            staff_checklist=["了解具体睡眠困难类型", "询问夜间疼痛、起夜、心慌或情绪影响", "观察白天精神状态"],
            family_safe_summary="老人反映昨晚睡眠不好，护理员将进一步了解原因和白天精神状态。",
            red_flag_checks_needed=["明显胸闷或心慌", "白天意识或精神状态明显改变"],
            confidence="fallback",
        )
        return _result_from_detail(detail)

    if _is_shoulder_back_soreness(text):
        detail = ObservationDetail(
            raw_quote=text,
            domain="pain",
            specific_problem="肩膀和背部酸痛",
            body_location="肩膀和背部",
            sensation_quality="酸",
            missing_information=[
                "是今天刚出现还是持续几天",
                "是否活动后、久坐、受凉或睡姿有关",
                "是否伴随胸闷、气短、出汗、摔倒或疼痛加重",
            ],
            next_best_question="这种酸痛是今天刚出现，还是已经有几天了？有没有摔倒、胸闷、气短、出汗，或者越来越痛？",
            staff_checklist=["确认酸痛开始时间", "询问活动、久坐、受凉或睡姿", "观察活动是否受影响"],
            family_safe_summary="老人反映肩膀和背部酸痛，护理员将确认持续时间、诱因及是否加重。",
            red_flag_checks_needed=["胸闷", "气短", "出汗", "摔倒", "疼痛明显加重"],
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
            next_best_question="是哪只手麻？是突然出现的吗？有没有同时没力、说话不清、脸歪或走路不稳？",
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
            next_best_question="头痛是突然一下子很严重，还是慢慢开始的？有没有呕吐、看不清、说话不清，或者手脚没力？",
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
            next_best_question="您是身体不舒服但不想麻烦家人，还是最近心情不好、担心家人，或更想一个人待着？",
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
        recommended_elder_response=_format_elder_response(detail),
        recommended_staff_handoff=(
            f"老人原话：{detail.raw_quote}。具体情况：{detail.specific_problem}。"
            f"请重点确认：{'；'.join(detail.staff_checklist)}。"
        ),
        recommended_family_summary_after_confirmation=detail.family_safe_summary,
    )


def _format_elder_response(detail: ObservationDetail) -> str:
    report = detail.raw_quote.rstrip("。.!！")
    return f"我听到您说：{report}。请您再告诉我：{detail.next_best_question}"


def _is_shoulder_back_soreness(text: str) -> bool:
    has_location = _has_any(text, ("肩膀", "肩", "背", "腰", "胳膊", "腿", "关节", "肌肉"))
    return has_location and _has_any(text, ("酸", "酸痛", "疼", "痛"))


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)
