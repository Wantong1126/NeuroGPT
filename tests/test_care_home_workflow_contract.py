# SPDX-License-Identifier: MIT
"""Care-home workflow payload contract tests."""

from __future__ import annotations

from pipeline.orchestrator import run_pipeline, to_mvp_response_payload


DIAGNOSIS_CLAIMS = ["确诊", "一定是", "你得了", "diagnosed as", "definitely"]


def _payload_for(text: str, session_id: str = "care-home"):
    state, output = run_pipeline(f"{session_id}-{abs(hash(text))}", text)
    return state, output, to_mvp_response_payload(state, output)


def _combined_staff_text(payload) -> str:
    handoff = payload.care_home_handoff
    daily = payload.daily_report_item
    assert handoff is not None
    assert daily is not None
    return "\n".join(
        [
            handoff.resident_summary,
            "\n".join(handoff.known_facts),
            "\n".join(handoff.missing_critical_info),
            handoff.risk_status,
            handoff.escalation_reason or "",
            handoff.recommended_staff_action,
            "\n".join(handoff.follow_up_tasks),
            "\n".join(handoff.suggested_next_observations),
            handoff.caregiver_brief,
            daily.headline,
            daily.category,
            daily.summary_for_department,
            "\n".join(daily.unresolved_questions),
        ]
    )


def assert_no_diagnosis_claims(text: str) -> None:
    lowered = text.lower()
    for phrase in DIAGNOSIS_CLAIMS:
        assert phrase.lower() not in lowered


def test_emergency_neuro_case_builds_staff_handoff_and_daily_report() -> None:
    _state, _output, payload = _payload_for(
        "老人突然右手没力，说话不清",
        "care-home-emergency-neuro",
    )

    handoff = payload.care_home_handoff
    daily = payload.daily_report_item

    assert payload.action_level == "emergency_now"
    assert handoff is not None
    assert daily is not None
    assert daily.escalation_needed is True
    assert daily.action_level == "emergency_now"
    assert daily.category in {"neuro_symptom", "general_monitoring"}
    assert any("起病" in task and "持续" in task for task in handoff.follow_up_tasks)
    assert any("说话" in task for task in handoff.follow_up_tasks)
    assert any("面部" in task for task in handoff.follow_up_tasks)
    assert any("手臂" in task or "腿部" in task for task in handoff.follow_up_tasks)
    assert "居民" in handoff.resident_summary
    assert handoff.recommended_staff_action
    assert_no_diagnosis_claims(_combined_staff_text(payload))


def test_monitor_or_ambiguous_sensory_case_has_conservative_staff_tasks() -> None:
    _state, _output, payload = _payload_for(
        "老人突然左手一指二指发麻，前臂刺痛，手腕僵直",
        "care-home-sensory-monitor",
    )

    handoff = payload.care_home_handoff
    daily = payload.daily_report_item

    assert handoff is not None
    assert daily is not None
    assert daily.escalation_needed is (payload.action_level in {"emergency_now", "same_day_review"})
    assert any("持续" in task for task in handoff.follow_up_tasks)
    assert any("加重" in task for task in handoff.follow_up_tasks)
    assert any("新的单侧无力" in task for task in handoff.follow_up_tasks)
    assert handoff.missing_critical_info
    assert handoff.caregiver_brief
    assert_no_diagnosis_claims(_combined_staff_text(payload))


def test_psychological_wellbeing_case_preserves_staff_review_context() -> None:
    _state, _output, payload = _payload_for(
        "老人最近总说自己没意思，不想见人，晚上睡不好",
        "care-home-psychological",
    )

    handoff = payload.care_home_handoff
    daily = payload.daily_report_item

    assert handoff is not None
    assert daily is not None
    assert daily.category in {"psychological_wellbeing", "general_monitoring"}
    assert "居民" in handoff.resident_summary
    assert any("情绪" in task for task in handoff.follow_up_tasks)
    assert any("睡眠" in task for task in handoff.follow_up_tasks)
    assert any("社交" in task for task in handoff.follow_up_tasks)
    assert any("情绪" in item or "睡眠" in item or "社交" in item for item in handoff.missing_critical_info)
    assert_no_diagnosis_claims(_combined_staff_text(payload))


def test_care_home_fields_are_serialized_in_mvp_payload() -> None:
    _state, _output, payload = _payload_for(
        "sudden right arm weakness and face droop",
        "care-home-serialization",
    )

    data = payload.model_dump(mode="json")

    assert "care_home_handoff" in data
    assert "daily_report_item" in data
    assert data["care_home_handoff"]["known_facts"]
    assert data["care_home_handoff"]["follow_up_tasks"]
    assert data["daily_report_item"]["headline"]
    assert data["daily_report_item"]["summary_for_department"]
