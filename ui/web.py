# SPDX-License-Identifier: MIT
"""Minimal Flask UI for NeuroGPT."""
from __future__ import annotations

import os
from typing import Any

from flask import Flask, redirect, render_template, request, session, url_for

from core.provider_settings import load_provider_config
from core.session import create_session, delete_session, load_session, save_session
from core.types import CaseState
from pipeline.orchestrator import run_pipeline

SESSION_KEY = "neurogpt_session_id"



def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates")
    app.config["SECRET_KEY"] = os.environ.get("NEUROGPT_FLASK_SECRET", "neurogpt-dev-secret")

    @app.get("/")
    def index() -> str:
        state = _get_or_create_state()
        return render_template("index.html", **_build_view_model(state))

    @app.post("/chat")
    def chat() -> str:
        user_input = request.form.get("user_input", "").strip()
        state = _get_or_create_state()
        if user_input:
            state, _output = run_pipeline(state.session_id, user_input, state)
            save_session(state)
        return render_template("index.html", **_build_view_model(state))

    @app.post("/reset")
    def reset() -> Any:
        session_id = session.get(SESSION_KEY)
        if session_id:
            delete_session(session_id)
        session.pop(SESSION_KEY, None)
        return redirect(url_for("index"))

    return app



def _get_or_create_state() -> CaseState:
    session_id = session.get(SESSION_KEY)
    if session_id:
        state = load_session(session_id)
        if state is not None:
            return state

    state = create_session()
    session[SESSION_KEY] = state.session_id
    save_session(state)
    return state



def _build_view_model(state: CaseState) -> dict[str, Any]:
    assistant_output = state.follow_up_question if state.needs_follow_up_question else state.user_message
    provider_config = load_provider_config()
    return {
        "session_id": state.session_id,
        "messages": [message.model_dump() for message in state.conversation_history],
        "assistant_output": assistant_output,
        "follow_up_question": state.follow_up_question,
        "caregiver_summary": state.caregiver_summary,
        "concern_level": state.concern_level.value,
        "action_level": state.action_level.value,
        "hesitation_flags": state.hesitation_flags,
        "provider_config": provider_config,
    }
