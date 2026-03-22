# SPDX-License-Identifier: MIT
"""
NeuroGPT v2 — Pipeline State
Helpers and initializers for CaseState.
Re-exports CaseState from core.types for pipeline-level imports.
"""

from core.types import (
    CaseState,
    ConcernLevel,
    ActionLevel,
    ConversationMessage,
)

__all__ = ["CaseState", "ConcernLevel", "ActionLevel", "ConversationMessage"]


def new_case(session_id: str, user_input: str = "") -> CaseState:
    """Create a fresh CaseState for a new session or new turn."""
    state = CaseState(session_id=session_id, turn_count=0)
    if user_input:
        state.add_user_message(user_input)
    return state
