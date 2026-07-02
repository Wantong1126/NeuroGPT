# SPDX-License-Identifier: MIT
from __future__ import annotations

from core.session import delete_session, load_session
from ui.web import create_app



def test_product_routes_load() -> None:
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    routes = ["/", "/elder", "/staff", "/family", "/admin"]

    for route in routes:
        response = client.get(route)
        assert response.status_code == 200

    assert b"Choose the area that matches your role" in client.get("/").data



def test_flask_route_persists_case_state_across_requests() -> None:
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

    delete_session(session_id)


def test_reset_replaces_current_elder_session() -> None:
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    client.get("/elder")
    with client.session_transaction() as flask_session:
        original_session_id = flask_session["neurogpt_session_id"]

    response = client.post("/reset")

    assert response.status_code == 302
    assert load_session(original_session_id) is None
