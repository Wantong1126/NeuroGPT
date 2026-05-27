# SPDX-License-Identifier: MIT
"""Tests for the local static demo UI served by the MVP API app."""
from __future__ import annotations

from ui.api import SESSION_STATES, create_app


def _client():
    SESSION_STATES.clear()
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_local_demo_page_loads() -> None:
    client = _client()

    response = client.get("/")

    assert response.status_code == 200
    assert b"NeuroGPT Local Demo" in response.data
    assert b"/api/chat" in response.data


def test_static_ui_assets_load() -> None:
    client = _client()

    script = client.get("/static/app.js")
    styles = client.get("/static/styles.css")

    assert script.status_code == 200
    assert b"fetch(\"/api/chat\"" in script.data
    assert b"debug-panel" in script.data
    assert styles.status_code == 200
    assert b".debug-panel" in styles.data


def test_local_ui_api_chat_still_returns_valid_payload() -> None:
    client = _client()

    response = client.post("/api/chat", json={"message": "sudden right arm weakness and face droop"})
    payload = response.get_json()["payload"]

    assert response.status_code == 200
    assert payload["action_level"] == "emergency_now"
    assert payload["user_message"]
    assert "debug_metadata" in payload


def test_local_ui_reset_still_works() -> None:
    client = _client()

    client.post("/api/chat", json={"session_id": "ui-reset", "message": "my right hand feels weak"})
    assert "ui-reset" in SESSION_STATES

    response = client.post("/api/reset", json={"session_id": "ui-reset"})

    assert response.status_code == 200
    assert response.get_json()["reset"] is True
    assert "ui-reset" not in SESSION_STATES
