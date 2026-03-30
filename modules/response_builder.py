# SPDX-License-Identifier: MIT
"""NeuroGPT v2 - Response Builder."""
from __future__ import annotations

from core.types import CaseState, ElderResponse, ActionStep
from core.config_loader import load_yaml_config

DEFAULT_ACTIONS = {
    "emergency_now": {
        "urgency": "建议立即就医或呼叫急救。",
        "steps": [
            {"action": "立即拨打急救电话或前往急诊", "reason": "当前症状符合高风险神经系统警讯。"},
            {"action": "记录症状开始时间", "reason": "急诊医生需要判断是否属于突发事件窗口期。"},
        ],
    },
    "same_day_review": {
        "urgency": "建议今天内尽快就医。",
        "steps": [
            {"action": "今天联系门诊或急诊", "reason": "症状需要尽快由医生评估。"},
        ],
    },
    "prompt_follow_up": {
        "urgency": "建议尽快预约医生评估。",
        "steps": [
            {"action": "48 小时内预约就诊", "reason": "症状需要专业评估，但暂未见到急救级别表现。"},
        ],
    },
    "monitor": {
        "urgency": "目前可先观察，但如果加重应尽快就医。",
        "steps": [
            {"action": "记录症状变化", "reason": "便于后续就诊时提供病程线索。"},
        ],
    },
}



def _load_action_tiers() -> dict:
    try:
        config = load_yaml_config("configs/action_tiers.yaml")
    except Exception:
        return DEFAULT_ACTIONS

    if "action_tiers" in config and isinstance(config["action_tiers"], dict):
        return config["action_tiers"]

    return config if isinstance(config, dict) else DEFAULT_ACTIONS



def build_response(state: CaseState) -> ElderResponse:
    """Build an elder-facing response from populated CaseState."""
    action_tiers = _load_action_tiers()
    disclaimer_cfg = load_yaml_config("configs/disclaimers.yaml")

    tier_key = state.action_level.value if state.action_level else "monitor"
    tier_data = action_tiers.get(tier_key, DEFAULT_ACTIONS["monitor"])

    steps = [
        ActionStep(
            step_number=index,
            action=item.get("action", ""),
            reason=item.get("reason", ""),
            what_to_say=item.get("what_to_say", ""),
        )
        for index, item in enumerate(tier_data.get("steps", []), start=1)
    ]

    if state.concern_level.value in ("high", "moderate"):
        empathy = "感谢你把这些情况说出来，这些信息值得认真对待。"
    else:
        empathy = "我先帮你把症状整理清楚。"

    what_this_means = state.plain_language_rationale or state.why_not_normal_ageing
    disclaimer = disclaimer_cfg.get("disclaimers", {}).get("general", {}).get("short", "")

    return ElderResponse(
        empathy_statement=empathy,
        what_this_means=what_this_means,
        urgency_statement=tier_data.get("urgency", DEFAULT_ACTIONS["monitor"]["urgency"]),
        action_steps=steps,
        disclaimer=disclaimer,
        monitor_points=tier_data.get("monitor_points", []),
    )
