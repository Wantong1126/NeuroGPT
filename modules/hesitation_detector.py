# SPDX-License-Identifier: MIT
"""NeuroGPT v2 — Hesitation Detector. Detects minimization/delay/avoidance/burden language."""
from __future__ import annotations
import re
from core.types import CaseState
from core.config_loader import load_yaml_config

# Load patterns lazily
_PATTERNS: dict | None = None

def _load_patterns():
    global _PATTERNS
    if _PATTERNS is None:
        _PATTERNS = load_yaml_config("configs/hesitation_patterns.yaml")
    return _PATTERNS

def detect_hesitation(state: CaseState) -> list[str]:
    """Returns list of matched hesitation type labels."""
    config = _load_patterns()
    text = state.raw_user_input.lower()
    matched = []
    for group in config.get("hesitation_types", {}).values():
        for pattern in group.get("patterns", []):
            if pattern.lower() in text:
                matched.append(group["label"])
                break
    return matched
