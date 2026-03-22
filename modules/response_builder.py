# SPDX-License-Identifier: MIT
"""NeuroGPT v2 — Response Builder. Assembles user-facing message from CaseState."""
from __future__ import annotations
from core.types import CaseState, ActionLevel, ElderResponse, ActionStep
from core.config_loader import load_yaml_config

def build_response(state: CaseState) -> ElderResponse:
    """Build ElderResponse from populated CaseState."""
    action_cfg = load_yaml_config("configs/action_tiers.yaml")
    disclaimer_cfg = load_yaml_config("configs/disclaimers.yaml")
    action_tiers = action_cfg.get("action_tiers", {})
    tier_key = state.action_level.value if state.action_level else "monitor"
    tier_data = action_tiers.get(tier_key, {})
    urgency = tier_data.get("urgency", "")
    steps_raw = tier_data.get("steps", [])
    steps = [ActionStep(step_number=i+1, action=s.get("action",""), reason=s.get("reason","")) for i,s in enumerate(steps_raw)]
    empathy = "感谢您告诉我这些，我会认真对待您描述的情况。" if state.concern_level.value in ("high","moderate") else "好的，我来帮您梳理一下。"
    why_not = getattr(state, "why_not_ageing", "")
    return ElderResponse(
        empathy_statement=empathy,
        what_this_means=state.plain_language_rationale or why_not,
        urgency_statement=urgency,
        action_steps=steps,
        disclaimer=disclaimer_cfg.get("disclaimers", {}).get("general", {}).get("short", ""),
        monitor_points=tier_data.get("monitor_points", []),
    )
