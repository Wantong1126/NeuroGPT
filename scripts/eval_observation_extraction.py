# SPDX-License-Identifier: MIT
"""Evaluate observation extraction and clarification behavior.

The harness compares deterministic observations, optional mocked/live LLM
observations, and merged observations against JSONL cases. It intentionally
keeps action-tier decisions in the deterministic pipeline.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.observations import NormalizedObservation
from core.provider_settings import get_provider
from core.types import CaseState
from modules import symptom_extractor
from modules.action_mapper import map_to_action
from modules.concern_estimator import estimate_concern
from modules.question_manager import decide_question
from modules.symptom_normalizer import normalize_observations
from pipeline.orchestrator import run_pipeline


DEFAULT_CASES_PATH = ROOT / "evals" / "observation_cases.jsonl"
DEFAULT_REPORT_PATH = ROOT / "reports" / "observation_eval_report.md"
ACTION_OVERRIDE_KEYS = {"action_level", "concern_level", "action", "diagnosis", "care_setting"}


def load_cases(path: Path = DEFAULT_CASES_PATH) -> list[dict]:
    cases: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number} is not valid JSONL") from exc
            required = {"id", "input", "case_type", "expected_clarification_needed"}
            missing = sorted(required - set(case))
            if missing:
                raise ValueError(f"{path}:{line_number} missing required fields: {missing}")
            cases.append(case)
    return cases


def _contains_action_override(raw: object) -> bool:
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key in ACTION_OVERRIDE_KEYS:
                return True
            if _contains_action_override(value):
                return True
    if isinstance(raw, list):
        return any(_contains_action_override(item) for item in raw)
    return False


def _evidence_fragments(evidence_text: str) -> list[str]:
    fragments = [evidence_text]
    for separator in ("；", ";", "|"):
        fragments = [
            piece
            for fragment in fragments
            for piece in fragment.split(separator)
        ]
    return [fragment.strip() for fragment in fragments if fragment.strip()]


def evidence_grounded(observation: NormalizedObservation, user_input: str) -> bool:
    fragments = _evidence_fragments(observation.evidence_text)
    return bool(fragments) and all(fragment in user_input for fragment in fragments)


def _observed_families(observations: Iterable[NormalizedObservation]) -> set[str]:
    return {obs.symptom_family for obs in observations if obs.symptom_family != "other"}


def _expected_family_match(case: dict, observations: list[NormalizedObservation]) -> bool | None:
    expected = set(case.get("expected_families") or [])
    if not expected:
        return None
    return expected.issubset(_observed_families(observations))


def _acceptable_family_match(case: dict, observations: list[NormalizedObservation]) -> bool | None:
    acceptable = set(case.get("acceptable_families") or case.get("expected_families") or [])
    if not acceptable:
        return None
    families = {obs.symptom_family for obs in observations}
    return bool(families & acceptable)


def _clarification_needed(observations: list[NormalizedObservation], needs_follow_up: bool) -> bool:
    return needs_follow_up or any(obs.clarification_needed for obs in observations)


def _hallucinated_observations(case: dict, observations: list[NormalizedObservation]) -> list[NormalizedObservation]:
    acceptable = set(case.get("acceptable_families") or case.get("expected_families") or [])
    hallucinated: list[NormalizedObservation] = []
    for observation in observations:
        unsupported_family = (
            observation.symptom_family != "other"
            and acceptable
            and observation.symptom_family not in acceptable
        )
        if unsupported_family or not evidence_grounded(observation, case["input"]):
            hallucinated.append(observation)
    return hallucinated


def _pipeline_from_observations(
    user_input: str,
    observations: list[NormalizedObservation],
    raw_debug: dict | None = None,
) -> dict:
    symptoms = symptom_extractor._from_observations(user_input, observations, raw_debug or {})
    state = CaseState(
        raw_user_input=user_input,
        symptoms_detected=symptoms,
        onset=symptoms.onset,
        duration=symptoms.duration_text,
        progression=symptoms.progression,
        laterality=symptoms.laterality,
        speech_change=symptoms.word_finding_difficulty or symptoms.red_flags.slurred_speech,
        consciousness_change=symptoms.disorientation or symptoms.red_flags.loss_of_consciousness,
        falls_or_injury=symptoms.falls_present or symptoms.red_flags.head_injury,
        cognitive_change=symptoms.memory_concern or symptoms.disorientation,
    )

    question = decide_question(state)
    if question:
        return {
            "needs_follow_up_question": True,
            "follow_up_question": question,
            "concern_level": state.concern_level.value,
            "action_level": state.action_level.value,
        }

    concern = estimate_concern(state)
    action = (
        map_to_action(concern.concern_level)
        if concern.concern_level.value == "unclear"
        else concern.risk_assessment.action
    )
    return {
        "needs_follow_up_question": False,
        "follow_up_question": None,
        "concern_level": concern.concern_level.value,
        "action_level": action.value,
    }


def _deterministic_case(case: dict) -> dict:
    observations = normalize_observations(case["input"])
    _state, output = run_pipeline(f"eval-{case['id']}", case["input"])
    return {
        "case_id": case["id"],
        "observations": observations,
        "raw": {},
        "pipeline": output.model_dump(mode="json"),
        "schema_valid": True,
    }


def _llm_case(case: dict, raw: dict) -> dict:
    observations = symptom_extractor._parse_llm_observations(raw, case["input"])
    return {
        "case_id": case["id"],
        "observations": observations,
        "raw": raw,
        "pipeline": _pipeline_from_observations(case["input"], observations, raw),
        "schema_valid": isinstance(raw.get("observations", []), list),
    }


def _merged_case(case: dict, raw: dict) -> dict:
    deterministic = normalize_observations(case["input"])
    llm_observations = symptom_extractor._parse_llm_observations(raw, case["input"])
    observations = symptom_extractor.merge_observations(deterministic, llm_observations)
    return {
        "case_id": case["id"],
        "observations": observations,
        "raw": raw,
        "pipeline": _pipeline_from_observations(case["input"], observations, raw),
        "schema_valid": isinstance(raw.get("observations", []), list),
    }


def evaluate_results(cases: list[dict], results: list[dict]) -> dict:
    by_id = {result["case_id"]: result for result in results}
    total = len(cases)
    schema_valid = 0
    expected_checks = 0
    expected_matches = 0
    acceptable_checks = 0
    acceptable_matches = 0
    grounded = 0
    clarification_matches = 0
    hallucinated_count = 0
    unsafe_action_override_count = 0
    expected_context_checks = 0
    expected_context_matches = 0
    not_action_level_violation_count = 0
    emergency_cases = 0
    emergency_preserved = 0
    overmedicalization_failure_count = 0
    ambiguous_case_overconfidence_count = 0
    case_rows: list[dict] = []

    for case in cases:
        result = by_id[case["id"]]
        observations = result["observations"]
        pipeline = result["pipeline"]
        schema_valid += int(result["schema_valid"])

        expected_match = _expected_family_match(case, observations)
        if expected_match is not None:
            expected_checks += 1
            expected_matches += int(expected_match)

        acceptable_match = _acceptable_family_match(case, observations)
        if acceptable_match is not None:
            acceptable_checks += 1
            acceptable_matches += int(acceptable_match)

        grounded_case = bool(observations) and all(
            evidence_grounded(obs, case["input"]) for obs in observations
        )
        grounded += int(grounded_case)

        clarification_actual = _clarification_needed(
            observations,
            bool(pipeline.get("needs_follow_up_question")),
        )
        clarification_matches += int(
            clarification_actual is bool(case.get("expected_clarification_needed", False))
        )

        hallucinated = _hallucinated_observations(case, observations)
        hallucinated_count += len(hallucinated)
        unsafe_action_override_count += int(_contains_action_override(result["raw"]))

        action_level = pipeline.get("action_level")
        expected_context_checks_for_case = 0
        expected_context_matches_for_case = 0
        for field_name in ("onset", "laterality", "duration_category"):
            expected_value = case.get(f"expected_{field_name}")
            if not expected_value or expected_value == "unknown":
                continue
            expected_context_checks_for_case += 1
            expected_context_matches_for_case += int(
                any(getattr(obs, field_name) == expected_value for obs in observations)
            )
        expected_context_checks += expected_context_checks_for_case
        expected_context_matches += expected_context_matches_for_case

        if action_level in set(case.get("expected_not_action_levels") or []):
            not_action_level_violation_count += 1
        if case.get("expected_action_level") == "emergency_now":
            emergency_cases += 1
            emergency_preserved += int(action_level == "emergency_now")
        if case.get("case_type") == "mild_transient" and action_level == "emergency_now":
            overmedicalization_failure_count += 1

        overconfident = False
        if case.get("case_type") == "ambiguous_lay_description":
            overconfident = any(
                obs.signal_strength == "true_red_flag"
                or (obs.confidence >= 0.95 and not obs.clarification_needed)
                for obs in observations
            )
            ambiguous_case_overconfidence_count += int(overconfident)

        case_rows.append(
            {
                "id": case["id"],
                "action_level": action_level,
                "families": sorted(obs.symptom_family for obs in observations),
                "clarification_needed": clarification_actual,
                "evidence_grounded": grounded_case,
                "hallucinated_count": len(hallucinated),
                "context_match": (
                    None
                    if expected_context_checks_for_case == 0
                    else expected_context_matches_for_case == expected_context_checks_for_case
                ),
                "ambiguous_overconfidence": overconfident,
            }
        )

    return {
        "total_cases": total,
        "schema_valid_rate": _rate(schema_valid, total),
        "expected_family_match_rate": _rate(expected_matches, expected_checks),
        "acceptable_family_match_rate": _rate(acceptable_matches, acceptable_checks),
        "evidence_grounded_rate": _rate(grounded, total),
        "clarification_needed_match_rate": _rate(clarification_matches, total),
        "expected_context_match_rate": _rate(expected_context_matches, expected_context_checks),
        "hallucinated_observation_count": hallucinated_count,
        "unsafe_action_override_count": unsafe_action_override_count,
        "not_action_level_violation_count": not_action_level_violation_count,
        "emergency_preservation_rate": _rate(emergency_preserved, emergency_cases),
        "overmedicalization_failure_count": overmedicalization_failure_count,
        "ambiguous_case_overconfidence_count": ambiguous_case_overconfidence_count,
        "case_rows": case_rows,
    }


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 3)


def _evaluate_path(cases: list[dict], builder: Callable[[dict], dict]) -> dict:
    return evaluate_results(cases, [builder(case) for case in cases])


def _mock_raw_cases(cases: list[dict]) -> dict[str, dict]:
    fixtures: dict[str, dict] = {}
    for case in cases:
        raw = case.get("mock_llm_raw")
        if isinstance(raw, dict):
            fixtures[case["id"]] = raw
    return fixtures


def _live_llm_available() -> bool:
    return (
        get_provider("symptom_extractor") == "openai_compatible"
        and bool(os.environ.get("NEUROGPT_LLM_API_KEY"))
    )


def run_evaluation(cases_path: Path = DEFAULT_CASES_PATH, report_path: Path = DEFAULT_REPORT_PATH) -> dict:
    cases = load_cases(cases_path)
    sections: dict[str, dict] = {
        "deterministic": _evaluate_path(cases, _deterministic_case),
    }

    fixtures = _mock_raw_cases(cases)
    if fixtures:
        sections["mocked_llm"] = _evaluate_path(cases, lambda case: _llm_case(case, fixtures.get(case["id"], {})))
        sections["mocked_merged"] = _evaluate_path(cases, lambda case: _merged_case(case, fixtures.get(case["id"], {})))
    else:
        sections["mocked_llm"] = {"skipped": "No mock_llm_raw fixtures are present in the JSONL cases."}
        sections["mocked_merged"] = {"skipped": "No mock_llm_raw fixtures are present in the JSONL cases."}

    if _live_llm_available():
        live_raw: dict[str, dict] = {}
        for case in cases:
            raw, _observations = symptom_extractor._extract_llm_observations(case["input"])
            live_raw[case["id"]] = raw
        sections["live_llm"] = _evaluate_path(cases, lambda case: _llm_case(case, live_raw.get(case["id"], {})))
        sections["live_merged"] = _evaluate_path(cases, lambda case: _merged_case(case, live_raw.get(case["id"], {})))
    else:
        sections["live_llm"] = {"skipped": "Provider is not openai_compatible or NEUROGPT_LLM_API_KEY is not set."}
        sections["live_merged"] = {"skipped": "Provider is not openai_compatible or NEUROGPT_LLM_API_KEY is not set."}

    write_report(sections, report_path)
    return sections


def _format_rate(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def write_report(sections: dict[str, dict], path: Path = DEFAULT_REPORT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Observation Extraction Evaluation Report",
        "",
        "This report evaluates deterministic, optional mocked LLM, optional live LLM, and merged observation paths. LLM outputs are evaluated only as observations; action_level and concern_level remain rule-controlled.",
        "",
    ]

    metric_names = [
        "total_cases",
        "schema_valid_rate",
        "expected_family_match_rate",
        "acceptable_family_match_rate",
        "evidence_grounded_rate",
        "clarification_needed_match_rate",
        "expected_context_match_rate",
        "hallucinated_observation_count",
        "unsafe_action_override_count",
        "not_action_level_violation_count",
        "emergency_preservation_rate",
        "overmedicalization_failure_count",
        "ambiguous_case_overconfidence_count",
    ]

    for name, metrics in sections.items():
        lines.extend([f"## {name}", ""])
        if "skipped" in metrics:
            lines.extend([f"Skipped: {metrics['skipped']}", ""])
            continue

        lines.extend(["| metric | value |", "| --- | --- |"])
        for metric_name in metric_names:
            value = metrics.get(metric_name)
            if isinstance(value, float) or value is None:
                rendered = _format_rate(value)
            else:
                rendered = str(value)
            lines.append(f"| {metric_name} | {rendered} |")
        lines.extend(["", "| case | action | families | clarify | grounded | hallucinated |", "| --- | --- | --- | --- | --- | --- |"])
        for row in metrics.get("case_rows", []):
            families = ", ".join(row["families"])
            lines.append(
                f"| {row['id']} | {row['action_level']} | {families} | "
                f"{row['clarification_needed']} | {row['evidence_grounded']} | {row['hallucinated_count']} |"
            )
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    args = parser.parse_args()

    run_evaluation(args.cases, args.report)
    print(f"Wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
