# SPDX-License-Identifier: MIT
"""Demo-ready flow validation for NeuroGPT."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.orchestrator import run_pipeline



def _run(name: str, turns: list[str], checks) -> tuple[str, bool, dict]:
    state = None
    output = None
    for turn in turns:
        state, output = run_pipeline(name, turn, state)
    result = {
        "concern_level": output.concern_level,
        "action_level": output.action_level,
        "needs_follow_up": output.needs_follow_up_question,
        "hesitation_flags": list(state.hesitation_flags),
        "caregiver_summary": bool(state.caregiver_summary),
        "merged_onset": state.symptoms_detected.onset.value,
        "merged_laterality": state.symptoms_detected.laterality.value,
        "slurred_speech": state.symptoms_detected.red_flags.slurred_speech,
        "weakness_one_side": state.symptoms_detected.red_flags.weakness_one_side,
    }
    return name, checks(result), result



def main() -> int:
    scenarios = [
        (
            "single_turn_stroke",
            ["sudden left arm weakness with slurred speech this morning"],
            lambda r: (not r["needs_follow_up"]) and r["concern_level"] == "high" and r["action_level"] == "emergency_now",
        ),
        (
            "multi_turn_merge",
            ["left arm weakness", "started suddenly this morning with slurred speech"],
            lambda r: r["merged_onset"] == "sudden" and r["merged_laterality"] == "one_side" and r["slurred_speech"] and r["weakness_one_side"],
        ),
        (
            "hesitation_handling",
            ["I don't want to worry my family but there is sudden left arm weakness and slurred speech"],
            lambda r: bool(r["hesitation_flags"]) and r["concern_level"] == "high",
        ),
        (
            "caregiver_output",
            ["gradual both sides tremor over months and gait is getting worse"],
            lambda r: r["caregiver_summary"] and r["action_level"] in {"same_day_review", "prompt_follow_up", "emergency_now"},
        ),
    ]

    overall_ok = True
    for name, turns, checks in scenarios:
        scenario_name, passed, result = _run(name, turns, checks)
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {scenario_name}")
        print(result)
        overall_ok = overall_ok and passed

    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

