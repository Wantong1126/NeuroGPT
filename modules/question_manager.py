# SPDX-License-Identifier: MIT
"""
NeuroGPT v2 — Question Manager
Decides whether to ask a follow-up question and generates it.
Priority: one question at a time, field that most affects concern estimation.
"""

from __future__ import annotations

from core.types import CaseState, ExtractedSymptoms, Onset, Laterality, Progression


def decide_question(state: CaseState) -> str | None:
    """
    Given a populated CaseState, return the single most important
    follow-up question — or None if no more questions needed.

    Priority order (highest → lowest):
      1. onset          — sudden vs gradual changes everything for stroke risk
      2. laterality     — one-sided symptoms are higher concern
      3. progression    — worsening is more urgent than stable/chronic
      4. falls          — any new falls in an older adult are concerning
      5. cognitive_change — new confusion/disorientation needs clarifying
    """
    s: ExtractedSymptoms = state.symptoms_detected

    if s.onset == Onset.UNKNOWN:
        return "这个症状是从什么时候开始的？是突然发生的，还是慢慢出现的？"

    if s.laterality == Laterality.UNKNOWN:
        return "这种症状是只出现在身体的一侧，还是两侧都有？"

    if s.progression == Progression.UNKNOWN:
        return "最近这个症状有没有加重？比如越来越频繁，或者越来越严重？"

    if s.falls_present and not state.falls_or_injury:
        return "摔倒有没有受伤？比如撞到头，或者出现淤青、骨折？"

    if s.disorientation or s.memory_concern:
        return "老人家有没有出现思维混乱、不认人、或者说话前言不搭后语的情况？"

    # No more high-priority missing fields
    return None
