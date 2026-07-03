# SPDX-License-Identifier: MIT
from __future__ import annotations

from core import product_store
from core.session import delete_session, load_session
from ui.web import create_app



def test_product_routes_load(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    routes = ["/", "/elder", "/staff", "/family", "/admin"]

    for route in routes:
        response = client.get(route)
        assert response.status_code == 200

    home_response = client.get("/")
    assert "请选择您的使用入口" in home_response.get_data(as_text=True)
    assert "中文" in home_response.get_data(as_text=True)
    assert "?lang=en" in home_response.get_data(as_text=True)


def test_chinese_is_the_default_product_language(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    elder_page = client.get("/elder").get_data(as_text=True)

    assert '<html lang="zh-CN">' in elder_page
    assert "今天哪里不舒服，或者有什么想告诉护理员/家人？" in elder_page
    assert "可以直接说身体、睡眠、心情、行动、说话、记忆上的变化。" in elder_page
    assert "继续告诉我" in elder_page
    assert "提交" in elder_page
    assert "/elder?lang=en" in elder_page



def test_flask_route_persists_case_state_across_requests(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    client.get("/elder")
    with client.session_transaction() as flask_session:
        session_id = flask_session["neurogpt_session_id"]

    client.post("/elder/report", data={"user_input": "left arm weakness"})
    state_after_turn_one = load_session(session_id)
    assert state_after_turn_one is not None
    assert len(state_after_turn_one.conversation_history) >= 2

    response = client.post(
        "/elder/report",
        data={"user_input": "started suddenly this morning with slurred speech"},
    )
    state_after_turn_two = load_session(session_id)

    assert response.status_code == 200
    assert state_after_turn_two is not None
    assert state_after_turn_two.concern_level.value == "high"
    assert state_after_turn_two.action_level.value == "emergency_now"
    assert state_after_turn_two.symptoms_detected.red_flags.slurred_speech is True
    assert state_after_turn_two.symptoms_detected.red_flags.weakness_one_side is True

    resident = product_store.get_demo_resident()
    events = product_store.list_events_for_resident(resident.resident_id)
    assert len(events) == 2
    assert all(event.case_session_id == session_id for event in events)
    assert events[0].raw_report == "started suddenly this morning with slurred speech"

    delete_session(session_id)


def test_reset_replaces_current_elder_session(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(product_store, "PRODUCT_DATA_DIR", tmp_path / ".product_data")
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    client.get("/elder")
    with client.session_transaction() as flask_session:
        original_session_id = flask_session["neurogpt_session_id"]

    response = client.post("/reset")

    assert response.status_code == 302
    assert load_session(original_session_id) is None
