# SPDX-License-Identifier: MIT
"""Tests for the observation extraction evaluation harness."""

from __future__ import annotations

from pathlib import Path

from core.observations import NormalizedObservation
from modules.symptom_normalizer import normalize_observations
from scripts import eval_observation_extraction as obs_eval


def test_eval_cases_load_correctly() -> None:
    cases = obs_eval.load_cases()

    assert 25 <= len(cases) <= 40
    assert {case["case_type"] for case in cases} >= {
        "clear_red_flag",
        "missing_info",
        "mild_transient",
        "chronic_progressive",
        "ambiguous_lay_description",
    }
    assert all(case["id"] and case["input"] for case in cases)


def test_report_generation_works_without_api_key(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("NEUROGPT_LLM_API_KEY", raising=False)
    report = tmp_path / "observation_eval_report.md"

    sections = obs_eval.run_evaluation(report_path=report)

    assert report.exists()
    text = report.read_text(encoding="utf-8")
    assert "## deterministic" in text
    assert "## mocked_llm" in text
    assert "## mocked_merged" in text
    assert "## live_llm" in text
    assert "No mock_llm_raw fixtures" not in text
    assert sections["deterministic"]["total_cases"] >= 25
    assert "skipped" not in sections["mocked_llm"]
    assert "skipped" not in sections["mocked_merged"]


def test_ambiguous_cases_can_expect_clarification_needed() -> None:
    cases = obs_eval.load_cases()
    ambiguous_cases = [
        case for case in cases if case["case_type"] == "ambiguous_lay_description"
    ]

    assert ambiguous_cases
    assert all(case["expected_clarification_needed"] is True for case in ambiguous_cases)


def test_mocked_llm_action_and_concern_output_is_ignored() -> None:
    case = {
        "id": "mock_override",
        "input": "今天有点累，没什么别的症状",
        "case_type": "mild_transient",
        "expected_families": ["fatigue"],
        "acceptable_families": ["fatigue"],
        "expected_clarification_needed": False,
    }
    raw = {
        "action_level": "emergency_now",
        "concern_level": "high",
        "observations": [
            {
                "raw_text": case["input"],
                "symptom_family": "fatigue",
                "signal_strength": "possible",
                "onset": "unknown",
                "duration_text": "",
                "duration_category": "unknown",
                "laterality": "unknown",
                "progression": "unknown",
                "severity_qualifier": "mild",
                "transient_or_resolved": False,
                "associated_red_flags": [],
                "evidence_text": "有点累",
                "confidence": 0.9,
            }
        ],
    }

    result = obs_eval._llm_case(case, raw)
    metrics = obs_eval.evaluate_results([case], [result])

    assert metrics["unsafe_action_override_count"] == 1
    assert result["pipeline"]["action_level"] != "emergency_now"


def test_jsonl_mocked_llm_sections_are_not_skipped() -> None:
    sections = obs_eval.run_evaluation()

    assert "skipped" not in sections["mocked_llm"]
    assert "skipped" not in sections["mocked_merged"]
    assert sections["mocked_llm"]["total_cases"] > 0
    assert sections["mocked_merged"]["total_cases"] == sections["mocked_llm"]["total_cases"]


def test_mocked_merged_improves_fixture_subset_family_matching() -> None:
    cases = obs_eval.load_cases()
    fixtures = obs_eval._mock_raw_cases(cases)
    mocked_cases = [case for case in cases if case["id"] in fixtures]
    deterministic = obs_eval._evaluate_path(mocked_cases, obs_eval._deterministic_case)
    mocked_merged = obs_eval._evaluate_path(
        mocked_cases,
        lambda case: obs_eval._merged_case(case, fixtures[case["id"]]),
    )

    assert mocked_merged["acceptable_family_match_rate"] > deterministic["acceptable_family_match_rate"]
    assert mocked_merged["expected_family_match_rate"] >= deterministic["expected_family_match_rate"]


def test_jsonl_mock_safety_metrics_remain_intact() -> None:
    sections = obs_eval.run_evaluation()

    for section_name in ("mocked_llm", "mocked_merged"):
        metrics = sections[section_name]
        assert metrics["unsafe_action_override_count"] == 1
        assert metrics["emergency_preservation_rate"] == 1.0
        assert metrics["overmedicalization_failure_count"] == 0
        assert metrics["ambiguous_case_overconfidence_count"] == 0
        assert metrics["not_action_level_violation_count"] == 0
        assert metrics["evidence_grounded_rate"] == 1.0


def test_evidence_text_must_be_grounded_in_input() -> None:
    grounded = NormalizedObservation(
        raw_text="右手有点麻",
        symptom_family="sensory",
        evidence_text="有点麻",
    )
    hallucinated = NormalizedObservation(
        raw_text="右手有点麻",
        symptom_family="sensory",
        evidence_text="说话不清",
    )

    assert obs_eval.evidence_grounded(grounded, "右手有点麻") is True
    assert obs_eval.evidence_grounded(hallucinated, "右手有点麻") is False


def test_mild_transient_cases_are_not_emergency_now() -> None:
    cases = [
        case
        for case in obs_eval.load_cases()
        if case["case_type"] == "mild_transient"
    ]
    results = [obs_eval._deterministic_case(case) for case in cases]
    metrics = obs_eval.evaluate_results(cases, results)

    assert metrics["overmedicalization_failure_count"] == 0
    assert all(result["pipeline"]["action_level"] != "emergency_now" for result in results)


def test_clear_emergency_cases_remain_emergency_now() -> None:
    cases = [
        case
        for case in obs_eval.load_cases()
        if case.get("expected_action_level") == "emergency_now"
    ]
    results = [obs_eval._deterministic_case(case) for case in cases]
    metrics = obs_eval.evaluate_results(cases, results)

    assert metrics["emergency_preservation_rate"] == 1.0


def test_ambiguous_lay_wording_not_forced_into_true_red_flag() -> None:
    text = "右手像被棉花包住一样，不太听使唤"
    observations = normalize_observations(text)

    assert any(obs.clarification_needed for obs in observations)
    assert all(obs.signal_strength != "true_red_flag" for obs in observations)
