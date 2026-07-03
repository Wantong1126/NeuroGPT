# SPDX-License-Identifier: MIT
from __future__ import annotations

from core import product_store
from core.types import ActionLevel, CaseState, ConcernLevel


def _use_temporary_store(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")


def test_demo_resident_is_seeded_idempotently(monkeypatch, tmp_path) -> None:
    _use_temporary_store(monkeypatch, tmp_path)

    resident = product_store.get_demo_resident()
    loaded_again = product_store.get_demo_resident()

    assert resident == loaded_again
    assert resident.name == "王秀兰"
    assert resident.age == 82
    assert resident.room == "203床"
    assert resident.family_relationship == "女儿"
    assert resident.care_focus == ["睡眠", "记忆", "行动变化"]


def test_care_event_round_trip_and_latest_order(monkeypatch, tmp_path) -> None:
    _use_temporary_store(monkeypatch, tmp_path)
    resident = product_store.get_demo_resident()
    state = CaseState(
        session_id="case_123",
        concern_level=ConcernLevel.MODERATE,
        action_level=ActionLevel.SAME_DAY_REVIEW,
        needs_follow_up_question=True,
        follow_up_question="When did this start?",
        caregiver_summary="Please arrange a same-day review.",
    )

    first = product_store.create_care_event_from_state(
        state,
        resident.resident_id,
        "My balance feels worse.",
    )
    second = product_store.create_care_event_from_state(
        state,
        resident.resident_id,
        "It started this morning.",
    )

    events = product_store.list_events_for_resident(resident.resident_id)
    assert {event.event_id for event in events} == {first.event_id, second.event_id}
    assert product_store.get_latest_event_for_resident(resident.resident_id) == second
    assert second.case_session_id == "case_123"
    assert second.staff_status == product_store.StaffStatus.PENDING_CONFIRMATION
    assert second.family_report_ready is False


def test_staff_confirmation_makes_family_report_ready(monkeypatch, tmp_path) -> None:
    _use_temporary_store(monkeypatch, tmp_path)
    resident = product_store.get_demo_resident()
    event = product_store.create_care_event_from_state(
        CaseState(session_id="case_456"),
        resident.resident_id,
        "I did not sleep well.",
    )

    updated = product_store.update_event_staff_status(
        event.event_id,
        "confirmed",
        staff_note="Checked with resident at 09:30.",
    )

    assert updated is not None
    assert updated.staff_status == product_store.StaffStatus.CONFIRMED
    assert updated.staff_note == "Checked with resident at 09:30."
    assert updated.family_report_ready is True
    assert product_store.update_event_staff_status("event_missing", "confirmed") is None
