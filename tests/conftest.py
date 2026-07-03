# SPDX-License-Identifier: MIT
"""Shared test isolation for optional live LLM configuration."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _disable_live_llm_by_default(monkeypatch, request):
    from core import llm as llm_client
    from modules import elder_explanation_generator, symptom_extractor

    monkeypatch.delenv("NEUROGPT_LLM_API_KEY", raising=False)
    monkeypatch.setattr(llm_client, "API_KEY", "")
    if request.path.name != "test_provider_settings.py":
        monkeypatch.setattr(symptom_extractor, "get_provider", lambda _module: "heuristic")
    monkeypatch.setattr(elder_explanation_generator, "get_provider", lambda _module: "heuristic")
