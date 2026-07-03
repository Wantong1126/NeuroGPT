# SPDX-License-Identifier: MIT
"""Flask product shell for NeuroGPT v1."""
from __future__ import annotations

import os
from typing import Any

from flask import Flask, redirect, render_template, request, session, url_for

from core.product_store import (
    create_care_event_from_state,
    get_demo_resident,
    get_latest_event_for_resident,
)
from core.session import create_session, delete_session, load_session, save_session
from core.types import CaseState
from pipeline.orchestrator import run_pipeline

SESSION_KEY = "neurogpt_session_id"


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates")
    app.config["SECRET_KEY"] = os.environ.get("NEUROGPT_FLASK_SECRET", "neurogpt-dev-secret")

    @app.get("/")
    def home() -> str:
        return render_template("home.html")

    @app.get("/elder")
    def elder() -> str:
        state = _get_or_create_state()
        return render_template("elder.html", **_build_elder_view_model(state))

    @app.post("/elder/report")
    def elder_report() -> str:
        user_input = request.form.get("user_input", "").strip()
        state = _get_or_create_state()
        if user_input:
            state, _output = run_pipeline(state.session_id, user_input, state)
            save_session(state)
            resident = get_demo_resident()
            create_care_event_from_state(state, resident.resident_id, user_input)
        return render_template("elder.html", **_build_elder_view_model(state))

    @app.get("/staff")
    def staff() -> str:
        return render_template("staff.html", **_build_product_view_model())

    @app.get("/family")
    def family() -> str:
        return render_template("family.html", **_build_product_view_model())

    @app.get("/admin")
    def admin() -> str:
        return render_template("admin.html", **_build_product_view_model())

    @app.post("/reset")
    def reset() -> Any:
        session_id = session.get(SESSION_KEY)
        if session_id:
            delete_session(session_id)
        session.pop(SESSION_KEY, None)
        return redirect(url_for("elder"))

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


def _build_elder_view_model(state: CaseState) -> dict[str, Any]:
    return {
        "messages": [message.model_dump() for message in state.conversation_history],
        "assistant_output": state.user_message,
        "needs_follow_up": state.needs_follow_up_question,
    }


def _build_product_view_model() -> dict[str, Any]:
    resident = get_demo_resident()
    return {
        "resident": resident,
        "latest_event": get_latest_event_for_resident(resident.resident_id),
    }
