# SPDX-License-Identifier: MIT
"""NeuroGPT v2 — Concern Estimator.

Wraps RiskStratifier to produce a ConcernAssessment.
Implements Executive Plan Section 13 hybrid design:
  deterministic rules own safety thresholds;
  LLM interpretation used for explanation only.
If deterministic and LLM conflict: deterministic wins.
"""
from core.types import CaseState, ConcernLevel, ConcernAssessment, RiskLevel, RiskAssessment
from core.risk_stratifier import RiskStratifier


def estimate_concern(state: CaseState) -> ConcernAssessment:
    """
    Main entry point.
    Runs deterministic RiskStratifier, maps to ConcernLevel,
    generates explanation including why-not-'it's ageing' framing.
    """
    stratifier = RiskStratifier()
    risk: RiskAssessment = stratifier.stratify(state.symptoms_detected)

    # Map deterministic RiskLevel -> ConcernLevel
    concern_level = _map_to_concern(risk.risk_level)

    # Flag LLM-vs-deterministic conflict (if extractor set llm_conflict flag)
    conflict = getattr(state.symptoms_detected, "llm_conflict", False)

    # Deterministic safety wins: if rules say HIGH, always stay HIGH
    if risk.risk_level == RiskLevel.HIGH and conflict:
        concern_level = ConcernLevel.HIGH

    explanation, why_not = _build_explanation(concern_level, risk)
    key_factors = risk.key_warning_signs or []

    return ConcernAssessment(
        concern_level=concern_level,
        explanation=explanation,
        why_not_normal_ageing=why_not,
        key_concern_factors=key_factors,
        risk_assessment=risk,
        concern_vs_llm_conflict=bool(conflict),
    )


def _map_to_concern(risk_level: RiskLevel) -> ConcernLevel:
    return {
        RiskLevel.HIGH: ConcernLevel.HIGH,
        RiskLevel.MEDIUM: ConcernLevel.MODERATE,
        RiskLevel.LOW: ConcernLevel.LOW,
        RiskLevel.UNKNOWN: ConcernLevel.UNCLEAR,
    }.get(risk_level, ConcernLevel.UNCLEAR)


def _build_explanation(concern: ConcernLevel, risk: RiskAssessment) -> tuple[str, str]:
    """
    Returns (plain_language_explanation, why_not_normal_ageing).
    """
    templates = {
        ConcernLevel.HIGH: [
            "根据您描述的症状，有些迹象需要立即关注，不能等。",
        ],
        ConcernLevel.MODERATE: [
            "您描述的情况值得尽快找医生看看，不需要紧急到急诊，但也不要拖太久。",
        ],
        ConcernLevel.LOW: [
            "目前您描述的情况听起来相对稳定，但如果症状出现变化或加重，要及时关注。",
        ],
        ConcernLevel.UNCLEAR: [
            "仅凭目前的描述还难以判断，请回答几个问题，帮助我们更好地了解情况。",
        ],
    }

    explanation = templates.get(concern, templates[ConcernLevel.UNCLEAR])[0]

    if concern in (ConcernLevel.HIGH, ConcernLevel.MODERATE):
        why_not = (
            "有些症状在老年人中并不罕见，但它们背后可能有更严重的原因，"
            "不应该简单归结为'老了'就忽视。如果真的是严重问题的早期信号，"
            "及时就医能带来完全不同的结果。"
        )
    elif concern == ConcernLevel.LOW:
        why_not = (
            "目前没有发现明显的红旗症状，但请继续关注。"
            "如果症状出现变化或加重，随时可以重新评估。"
        )
    else:
        why_not = "需要更多信息才能做出准确判断，请回答上面的问题。"

    return explanation, why_not
