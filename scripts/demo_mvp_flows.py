# SPDX-License-Identifier: MIT
"""Print deterministic MVP response payloads for product demo scenarios.

This script does not call live LLM providers by default.
"""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules import symptom_extractor
from pipeline.orchestrator import run_pipeline, to_mvp_response_payload


ScenarioSetup = Callable[[], None]


def _noop() -> None:
    return None


@contextmanager
def _patched_extractor(provider: str, call_structured=None) -> Iterator[None]:
    original_get_provider = symptom_extractor.get_provider
    original_call_structured = symptom_extractor.call_structured
    symptom_extractor.get_provider = lambda _module: provider
    if call_structured is not None:
        symptom_extractor.call_structured = call_structured
    try:
        yield
    finally:
        symptom_extractor.get_provider = original_get_provider
        symptom_extractor.call_structured = original_call_structured


def _llm_timeout(*_args, **_kwargs):
    raise TimeoutError("demo provider timeout")


def _llm_success(*_args, **_kwargs):
    return {
        "observations": [
            {
                "raw_text": "right hand feels wrapped",
                "symptom_family": "sensory",
                "signal_strength": "possible",
                "onset": "unknown",
                "duration_text": "",
                "duration_category": "unknown",
                "laterality": "one_side",
                "progression": "unknown",
                "severity_qualifier": "unknown",
                "transient_or_resolved": False,
                "associated_red_flags": [],
                "evidence_text": "right hand feels wrapped",
                "confidence": 0.9,
            }
        ],
    }


def run_demo_scenarios() -> list[dict]:
    scenarios = [
        ("emergency_red_flag", "sudden right arm weakness and face droop", "heuristic", None),
        ("ambiguous_sensory", "my right hand feels weird and numb", "heuristic", None),
        (
            "mild_transient",
            "suddenly both sides felt numb after sitting but it went away",
            "heuristic",
            None,
        ),
        ("chronic_memory_decline", "memory getting worse over months", "heuristic", None),
        ("llm_failure_fallback", "sudden right arm weakness and face droop", "openai_compatible", _llm_timeout),
        ("llm_success_augmentation", "right hand feels wrapped", "openai_compatible", _llm_success),
    ]
    payloads: list[dict] = []
    for name, text, provider, llm_func in scenarios:
        with _patched_extractor(provider, llm_func):
            state, output = run_pipeline(f"demo-mvp-{name}", text)
            payload = to_mvp_response_payload(state, output).model_dump(mode="json")
            payloads.append({"scenario": name, "input": text, "payload": payload})
    return payloads


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(run_demo_scenarios(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
