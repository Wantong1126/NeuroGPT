# SPDX-License-Identifier: MIT
"""
NeuroGPT v2 鈥?Step 3: Risk Stratification Engine
Deterministic rule-based engine. Zero LLM calls.
Applies YAML rule definitions to ExtractedSymptoms.
"""

from __future__ import annotations

from core.models import (
    ActionLevel,
    ActionTier,
    ExtractedSymptoms,
    RedFlags,
    RiskAssessment,
    RiskBasis,
    RiskLevel,
)
from core.config_loader import load_yaml_config


# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# Rule Engine
# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

class RiskStratifier:
    """
    Loads risk_rules.yaml and evaluates extracted symptoms
    against all rule conditions in priority order.

    Priority order: HIGH 鈫?MEDIUM 鈫?LOW 鈫?UNKNOWN
    Returns the FIRST matching rule (highest severity).
    """

    def __init__(self):
        self.rules = load_yaml_config("configs/risk_rules.yaml")

    def stratify(self, symptoms: ExtractedSymptoms) -> RiskAssessment:
        """
        Main entry point. Returns RiskAssessment with risk level,
        recommended action, and human-readable explanation.
        """
        # 鈹€鈹€ Check HIGH rules first 鈹€鈹€
        high_match = self._check_section(symptoms, self.rules.get("high_risk", []))
        if high_match:
            return self._build_assessment(
                RiskLevel.HIGH,
                self._resolve_action(high_match, ActionTier.CALL_AMBULANCE),
                high_match,
                symptoms,
            )

        # 鈹€鈹€ MEDIUM rules 鈹€鈹€
        medium_match = self._check_section(symptoms, self.rules.get("medium_risk", []))
        if medium_match:
            return self._build_assessment(
                RiskLevel.MEDIUM,
                self._resolve_action(medium_match, ActionTier.SEE_DOCTOR_URGENT),
                medium_match,
                symptoms,
            )

        # 鈹€鈹€ LOW rules 鈹€鈹€
        low_match = self._check_section(symptoms, self.rules.get("low_risk", []))
        if low_match:
            return self._build_assessment(
                RiskLevel.LOW,
                self._resolve_action(low_match, ActionTier.SCHEDULE_ROUTINE),
                low_match,
                symptoms,
            )

        # 鈹€鈹€ Fallback: UNKNOWN 鈹€鈹€
        return self._build_unknown(symptoms)

    def _resolve_action(self, rule: dict, default: ActionTier) -> ActionLevel | ActionTier:
        action = rule.get("action")
        if not action:
            return default
        try:
            return ActionLevel(action)
        except ValueError:
            return default

    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    # Section checker
    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

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

            # 鈹€鈹€ Check onset 鈹€鈹€
            if "onset" in conditions:
                if symptoms.onset.value != conditions["onset"]:
                    continue  # condition not met, skip this rule

            if "onset_in" in conditions:
                if symptoms.onset.value not in conditions["onset_in"]:
                    continue

            # 鈹€鈹€ Check laterality 鈹€鈹€
            if "laterality" in conditions:
                if symptoms.laterality.value != conditions["laterality"]:
                    continue

            # 鈹€鈹€ Check progression 鈹€鈹€
            if "progression" in conditions:
                prog = conditions["progression"]
                if isinstance(prog, str):
                    if symptoms.progression.value != prog:
                        continue
                elif isinstance(prog, list):
                    if symptoms.progression.value not in prog:
                        continue

            # 鈹€鈹€ Check symptom boolean flags 鈹€鈹€
            checks = conditions.get("checks", [])
            if not checks:
                # No checks defined 鈥?rule matches by onset/laterality alone
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
            "speech_language_symptom": (
                rf.slurred_speech
                or symptoms.word_finding_difficulty
                or "speech" in symptoms.symptom_type
            ),
        }

        for check in checks:
            if isinstance(check, dict):
                # Simple boolean flag check
                for flag_name, flag_value in check.items():
                    if flag_name.startswith("OR:"):
                        # OR grouping 鈥?skip; handled by requires_all logic
                        continue
                    if flag_name == "onset":
                        if symptoms.onset.value == flag_value:
                            matched += 1
                        continue
                    if flag_name == "laterality":
                        if symptoms.laterality.value == flag_value:
                            matched += 1
                        continue
                    if flag_name == "progression":
                        if isinstance(flag_value, list):
                            if symptoms.progression.value in flag_value:
                                matched += 1
                        elif symptoms.progression.value == flag_value:
                            matched += 1
                        continue
                    if flag_name == "absence_of":
                        if all(not symptom_flags.get(item, False) for item in flag_value):
                            matched += 1
                        continue
                    if flag_name in symptom_flags:
                        if symptom_flags[flag_name] == flag_value:
                            matched += 1
                    elif flag_name == "OR":
                        # OR condition 鈥?check if any are True
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

    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    # Assessment builders
    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _build_assessment(
        self,
        risk_level: RiskLevel,
        action: ActionLevel | ActionTier,
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
            warning_signs.append("one-sided weakness")
        if rf.facial_droop:
            warning_signs.append("facial droop")
        if rf.slurred_speech or symptoms.word_finding_difficulty:
            warning_signs.append("speech disturbance")
        if rf.sudden_onset:
            warning_signs.append("sudden onset")
        if rf.acute_confusion:
            warning_signs.append("acute confusion")
        if rf.seizure:
            warning_signs.append("seizure")
        if rf.severe_headache:
            warning_signs.append("severe headache")
        if symptoms.gait_difficulty:
            warning_signs.append("gait difficulty")
        if symptoms.falls_present:
            warning_signs.append("recurrent falls")
        if symptoms.memory_concern:
            warning_signs.append("memory concern")

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
                primary_concern="Insufficient information to determine risk level.",
            ),
            urgency_explanation="Not enough information to stratify risk; seek clinical review.",
            key_warning_signs=[],
        )
