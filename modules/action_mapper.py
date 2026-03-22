# SPDX-License-Identifier: MIT
"""NeuroGPT v2 — Action Mapper. Maps ConcernLevel to ActionLevel."""
from core.types import ConcernLevel, ActionLevel

# Static mapping — loaded from configs/action_tiers.yaml in production
CONCERN_TO_ACTION = {
    ConcernLevel.HIGH: ActionLevel.EMERGENCY_NOW,
    ConcernLevel.MODERATE: ActionLevel.SAME_DAY_REVIEW,
    ConcernLevel.LOW: ActionLevel.MONITOR,
    ConcernLevel.UNCLEAR: ActionLevel.MONITOR,
}

def map_to_action(concern_level: ConcernLevel) -> ActionLevel:
    return CONCERN_TO_ACTION.get(concern_level, ActionLevel.MONITOR)
