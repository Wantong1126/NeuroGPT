# SPDX-License-Identifier: MIT
from __future__ import annotations

from core import product_store
from modules.observation_state_merger import merge_observation_turn
from pipeline.orchestrator import run_pipeline
from ui.web import create_app


def test_abdominal_answers_merge_into_one_active_observation() -> None:
    state, first = run_pipeline("abdominal-flow", "我早上起来突然肚子非常痛")

    assert state.pending_field == "body_location"
    assert "肚子突然明显疼痛" in first.user_message
    assert any(reason in first.user_message for reason in ("胃肠不适", "饮食", "胀气"))
    assert "具体哪个位置最痛" in (first.follow_up_question or "")

    state, second = run_pipeline("abdominal-flow", "上腹", state)
    assert state.active_observation["body_location"] == "上腹"
    assert state.pending_field == "sensation_quality"
    assert "更像是痛、胀" in (second.follow_up_question or "")
    assert any(reason in second.user_message for reason in ("胃部不适", "消化不良", "胀气"))
    assert second.user_message != f"已记录：上腹不舒服。请您再告诉我：{second.follow_up_question}"
    assert "哪里痛" not in second.user_message

    state, third = run_pipeline("abdominal-flow", "痛和胀", state)
    assert state.active_observation["raw_quote"] == "我早上起来突然肚子非常痛"
    assert state.active_observation["body_location"] == "上腹"
    assert state.active_observation["sensation_quality"] == "痛、胀"
    assert state.pending_field == "duration"
    assert "持续多久" in (third.follow_up_question or "")
    assert any(reason in third.user_message for reason in ("胃部不适", "消化不良", "胀气"))
    assert "哪里痛" not in third.user_message
    assert state.active_observation["answer_history"] == [
        {"field": "body_location", "answer": "上腹"},
        {"field": "sensation_quality", "answer": "痛和胀"},
    ]


def test_merger_preserves_known_location_when_quality_is_answered() -> None:
    previous = {
        "domain": "abdominal_digestive",
        "raw_quote": "我早上起来突然肚子非常痛",
        "body_location": "上腹",
        "answer_history": [{"field": "body_location", "answer": "上腹"}],
    }

    merged = merge_observation_turn(previous, "痛和胀", "更像是哪种不舒服？", "sensation_quality")

    assert merged["body_location"] == "上腹"
    assert merged["sensation_quality"] == "痛、胀"
    assert merged["raw_quote"] == previous["raw_quote"]


def test_abdominal_flow_stops_after_required_fields_are_checked() -> None:
    state, _ = run_pipeline("abdominal-complete", "我早上起来突然肚子非常痛")
    for answer, next_field in (
        ("上腹", "sensation_quality"),
        ("痛和胀", "duration"),
        ("半小时了，一直痛", "severity_progression"),
        ("比刚开始更痛，已经影响吃饭", "associated_symptoms"),
    ):
        state, output = run_pipeline("abdominal-complete", answer, state)
        assert state.pending_field == next_field
        assert output.needs_follow_up_question is True

    state, output = run_pipeline("abdominal-complete", "没有发热呕吐，也没有胸闷气短", state)

    assert state.pending_field is None
    assert output.needs_follow_up_question is False
    assert "已记录：上腹痛和胀" in output.user_message
    assert "胃部不适" in output.user_message
    assert "会提醒护理员尽快确认" in output.user_message
    assert state.active_observation["associated_symptoms_checked"] is True


def test_location_without_pending_question_does_not_create_abdominal_case() -> None:
    state, output = run_pipeline("orphan-location", "上腹")

    assert state.active_observation["domain"] == "general"
    assert state.active_observation["specific_problem"] == "上腹"
    assert "上腹不舒服" not in output.user_message


def test_new_topic_archives_abdominal_observation_instead_of_overwriting() -> None:
    state, _first = run_pipeline("abdominal-topic", "我早上起来突然肚子非常痛")
    state, second = run_pipeline("abdominal-topic", "我头也有点晕", state)

    assert state.observation_history[0]["raw_quote"] == "我早上起来突然肚子非常痛"
    assert state.active_observation["raw_quote"] == "我头也有点晕"
    assert len(state.observation_extraction["observations"]) == 2
    assert "头也有点晕" in second.user_message


def test_care_event_and_staff_page_keep_initial_report_and_answers(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()
    client.get("/elder")
    client.post("/elder/select", data={"resident_choice": product_store.DEMO_RESIDENT_ID})

    client.post("/elder/report", data={"user_input": "我早上起来突然肚子非常痛"})
    client.post("/elder/report", data={"user_input": "上腹"})
    client.post("/elder/report", data={"user_input": "痛和胀"})

    resident = product_store.get_demo_resident()
    event = product_store.get_latest_event_for_resident(resident.resident_id)
    assert event is not None
    assert len(product_store.list_events_for_resident(resident.resident_id)) == 1
    assert event.raw_report == "我早上起来突然肚子非常痛"
    observation = event.observation_extraction["active_observation_state"]
    assert observation["body_location"] == "上腹"
    assert observation["sensation_quality"] == "痛、胀"
    assert [entry["answer"] for entry in observation["answer_history"]] == ["上腹", "痛和胀"]

    staff_page = client.get("/staff").get_data(as_text=True)
    assert "我早上起来突然肚子非常痛" in staff_page
    assert "上腹" in staff_page
    assert "痛和胀" in staff_page
