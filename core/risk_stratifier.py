# SPDX-License-Identifier: MIT
"""
NeuroGPT v2 — Step 3: Risk Stratification Engine
Deterministic rule-based engine. Zero LLM calls.
Applies YAML rule definitions to ExtractedSymptoms.
"""

from __future__ import annotations

from core.models import (
    ActionTier,
    ExtractedSymptoms,
    RedFlags,
    RiskAssessment,
    RiskBasis,
    RiskLevel,
)
from core.config_loader import load_yaml_config


# ─────────────────────────────────────────────
# Rule Engine
# ─────────────────────────────────────────────

class RiskStratifier:
    """
    Loads risk_rules.yaml and evaluates extracted symptoms
    against all rule conditions in priority order.

    Priority order: HIGH → MEDIUM → LOW → UNKNOWN
    Returns the FIRST matching rule (highest severity).
    """

    def __init__(self):
        self.rules = load_yaml_config("configs/risk_rules.yaml")

    def stratify(self, symptoms: ExtractedSymptoms) -> RiskAssessment:
        """
        Main entry point. Returns RiskAssessment with risk level,
        recommended action, and human-readable explanation.
        """
        # ── Check HIGH rules first ──
        high_match = self._check_section(symptoms, self.rules.get("high_risk", []))
        if high_match:
            return self._build_assessment(
                RiskLevel.HIGH,
                ActionTier.CALL_AMBULANCE,
                high_match,
                symptoms,
            )

        # ── MEDIUM rules ──
        medium_match = self._check_section(symptoms, self.rules.get("medium_risk", []))
        if medium_match:
            return self._build_assessment(
                RiskLevel.MEDIUM,
                ActionTier.SEE_DOCTOR_URGENT,
                medium_match,
                symptoms,
            )

        # ── LOW rules ──
        low_match = self._check_section(symptoms, self.rules.get("low_risk", []))
        if low_match:
            return self._build_assessment(
                RiskLevel.LOW,
                ActionTier.SCHEDULE_ROUTINE,
                low_match,
                symptoms,
            )

        # ── Fallback: UNKNOWN ──
        return self._build_unknown(symptoms)

    # ─────────────────────────────────────────────
    # Section checker
    # ─────────────────────────────────────────────

    def _check_section(
        self, symptoms: ExtractedSymptoms, rules: list
    ) -> dict | None:
        """
        Iterate rules in order, return first match.
        Each rule has a `conditions` dict; ALL conditions must pass (AND logic),
        unless the rule has `requires_all: false` (OR logic across its checks).
        """
        rf = symptoms.red_flags

        for rule in rules:
            conditions = rule.get("conditions", {})
            requires_all = conditions.get("requires_all", True)

            # ── Check onset ──
            if "onset" in conditions:
                if symptoms.onset.value != conditions["onset"]:
                    continue  # condition not met, skip this rule

            # ── Check laterality ──
            if "laterality" in conditions:
                if symptoms.laterality.value != conditions["laterality"]:
                    continue

            # ── Check progression ──
            if "progression" in conditions:
                prog = conditions["progression"]
                if isinstance(prog, str):
                    if symptoms.progression.value != prog:
                        continue
                elif isinstance(prog, list):
                    if symptoms.progression.value not in prog:
                        continue

            # ── Check symptom boolean flags ──
            checks = conditions.get("checks", [])
            if not checks:
                # No checks defined — rule matches by onset/laterality alone
                return rule

            matched = self._eval_checks(symptoms, rf, checks)

            if requires_all:
                # All checks must pass
                if matched == len(checks):
                    return rule
            else:
                # At least one check must pass
                if matched > 0:
                    return rule

        return None

    def _eval_checks(
        self, symptoms: ExtractedSymptoms, rf: RedFlags, checks: list
    ) -> int:
        """
        Evaluate a list of check conditions.
        Returns count of matched conditions.
        """
        matched = 0

        # Build a flat lookup for easier checking
        symptom_flags = {
            "weakness_one_side": rf.weakness_one_side,
            "facial_droop": rf.facial_droop,
            "slurred_speech": rf.slurred_speech,
            "sudden_onset": rf.sudden_onset,
            "acute_confusion": rf.acute_confusion,
            "seizure": rf.seizure,
            "loss_of_consciousness": rf.loss_of_consciousness,
            "severe_headache": rf.severe_headache,
            "vision_loss": rf.vision_loss,
            "gait_imbalance": rf.gait_imbalance,
            "focal_numbness": rf.focal_numbness,
            "new_falls": rf.new_falls,
            "head_injury": rf.head_injury,
            "incontinence": rf.incontinence,
            # Extended model fields
            "word_finding_difficulty": symptoms.word_finding_difficulty,
            "disorientation": symptoms.disorientation,
            "tremor_present": symptoms.tremor_present,
            "falls_present": symptoms.falls_present,
            "gait_difficulty": symptoms.gait_difficulty,
            "stiffness": symptoms.stiffness,
            "sleep_disturbance": symptoms.sleep_disturbance,
            "apathy": symptoms.apathy,
            "hallucinations": symptoms.hallucinations,
            "personality_change": symptoms.personality_change,
            "memory_concern": symptoms.memory_concern,
            "stroke_beFAST": rf.stroke_beFAST,
        }

        for check in checks:
            if isinstance(check, dict):
                # Simple boolean flag check
                for flag_name, flag_value in check.items():
                    if flag_name.startswith("OR:"):
                        # OR grouping — skip; handled by requires_all logic
                        continue
                    if flag_name in symptom_flags:
                        if symptom_flags[flag_name] == flag_value:
                            matched += 1
                    elif flag_name == "OR":
                        # OR condition — check if any are True
                        or_items = check["OR"]
                        for or_item in or_items:
                            if or_item in symptom_flags and symptom_flags[or_item]:
                                matched += 1
                                break  # count once
            elif isinstance(check, str):
                # Simpler format: just a boolean field name
                if check in symptom_flags and symptom_flags[check]:
                    matched += 1

        return matched

    # ─────────────────────────────────────────────
    # Assessment builders
    # ─────────────────────────────────────────────

    def _build_assessment(
        self,
        risk_level: RiskLevel,
        action: ActionTier,
        rule: dict,
        symptoms: ExtractedSymptoms,
    ) -> RiskAssessment:
        rf = symptoms.red_flags
        flag_count = sum([
            rf.weakness_one_side, rf.facial_droop, rf.slurred_speech,
            rf.sudden_onset, rf.acute_confusion, rf.seizure,
            rf.loss_of_consciousness, rf.severe_headache,
            rf.vision_loss, rf.gait_imbalance, rf.focal_numbness,
            rf.new_falls, rf.head_injury, rf.stroke_beFAST,
            symptoms.tremor_present, symptoms.falls_present,
            symptoms.gait_difficulty, symptoms.hallucinations,
            symptoms.memory_concern,
        ])

        # Build key warning signs list
        warning_signs = []
        if rf.weakness_one_side:
            warning_signs.append("单侧肢体无力")
        if rf.facial_droop:
            warning_signs.append("单侧面部下垂")
        if rf.slurred_speech or symptoms.word_finding_difficulty:
            warning_signs.append("言语含糊或找词困难")
        if rf.sudden_onset:
            warning_signs.append("突然起病")
        if rf.acute_confusion:
            warning_signs.append("急性意识混乱")
        if rf.seizure:
            warning_signs.append("癫痫发作")
        if rf.severe_headache:
            warning_signs.append("剧烈头痛")
        if symptoms.gait_difficulty:
            warning_signs.append("步态困难")
        if symptoms.falls_present:
            warning_signs.append("反复跌倒")
        if symptoms.memory_concern:
            warning_signs.append("认知功能下降")

        return RiskAssessment(
            risk_level=risk_level,
            action=action,
            basis=RiskBasis(
                rules_triggered=[rule.get("id", "unknown")],
                red_flags_count=flag_count,
                primary_concern=rule.get("description", ""),
            ),
            urgency_explanation=rule.get("description", ""),
            key_warning_signs=warning_signs,
        )

    def _build_unknown(self, symptoms: ExtractedSymptoms) -> RiskAssessment:
        return RiskAssessment(
            risk_level=RiskLevel.UNKNOWN,
            action=ActionTier.SEE_DOCTOR_URGENT,
            basis=RiskBasis(
                rules_triggered=["INSUFFICIENT_INFO"],
                red_flags_count=0,
                primary_concern="信息不足，无法判断风险等级。需要进一步询问",
            ),
            urgency_explanation="信息不足以做出判断，建议就医获取专业评估",
            key_warning_signs=[],
        )
