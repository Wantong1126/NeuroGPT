# SPDX-License-Identifier: MIT
"""NeuroGPT v2 — Concern Estimator."""
from core.types import CaseState, ConcernLevel, ConcernAssessment, RiskLevel, RiskAssessment
from core.risk_stratifier import assess_risk

def estimate_concern(state: CaseState) -> ConcernAssessment:
    risk: RiskAssessment = assess_risk(state.symptoms_detected)
    concern_level = _map_to_concern(risk.risk_level)
    conflict = getattr(state.symptoms_detected, "llm_conflict", False)
    if risk.risk_level == RiskLevel.HIGH and conflict:
        concern_level = ConcernLevel.HIGH
    explanation, why_not = _build_explanation(concern_level, risk)
    return ConcernAssessment(
        concern_level=concern_level,
        explanation=explanation,
        why_not_normal_ageing=why_not,
        key_concern_factors=risk.key_warning_signs or [],
        risk_assessment=risk,
        concern_vs_llm_conflict=bool(conflict),
    )

def _map_to_concern(risk):
    return {RiskLevel.HIGH: ConcernLevel.HIGH, RiskLevel.MEDIUM: ConcernLevel.MODERATE,
            RiskLevel.LOW: ConcernLevel.LOW, RiskLevel.UNKNOWN: ConcernLevel.UNCLEAR}.get(risk, ConcernLevel.UNCLEAR)

def _build_explanation(concern, risk):
    tpls = {ConcernLevel.HIGH: ["根据您描述的症状，有些迹象需要立即关注，不能等。"],
            ConcernLevel.MODERATE: ["您描述的情况值得尽快找医生看看，不需要紧急到急诊，但也不要拖太久。"],
            ConcernLevel.LOW: ["目前您描述的情况听起来相对稳定，但如果有变化或加重，还是要关注。"],
            ConcernLevel.UNCLEAR: ["仅凭目前的描述还难以判断，请回答几个问题。"]}
    expl = tpls.get(concern, tpls[ConcernLevel.UNCLEAR])[0]
    why = ("有些症状在老年人中并不罕见，但背后可能有更严重的原因，不应该简单归结为'老了'就忽视。"
           ) if concern in (ConcernLevel.HIGH, ConcernLevel.MODERATE) else ("需要更多信息才能做出判断。" )
    return expl, why
