# SPDX-License-Identifier: MIT
"""Flask product shell for NeuroGPT v1."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import Flask, redirect, render_template, request, session, url_for

from core.product_store import (
    CareEvent,
    Resident,
    create_resident,
    create_care_event_from_state,
    find_resident_by_exact_name,
    get_demo_resident,
    get_latest_event_for_resident,
    get_resident,
    list_events_for_resident,
    list_residents,
)
from core.session import create_session, delete_session, load_session, save_session
from core.types import CaseState
from pipeline.orchestrator import run_pipeline

SESSION_KEY = "neurogpt_session_id"
RESIDENT_KEY = "neurogpt_resident_id"
CHINA_TIMEZONE = timezone(timedelta(hours=8))

STAFF_STATUS_LABELS = {
    "pending_confirmation": "待护理员确认",
    "confirmed": "已确认",
    "monitoring": "持续关注",
    "family_contacted": "已联系家属",
    "offline_handled": "已线下处理",
}


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

    @app.post("/elder/select")
    def elder_select() -> Any:
        resident, error = _resolve_resident_selection()
        if error:
            state = _get_or_create_state()
            return render_template(
                "elder.html",
                **_build_elder_view_model(
                    state,
                    identity_error=error,
                    identity_choice=request.form.get("resident_choice", ""),
                    identity_name=request.form.get("resident_name", ""),
                    identity_room=request.form.get("resident_room", ""),
                ),
            )
        _select_resident(resident)
        return redirect(url_for("elder"))

    @app.post("/elder/report")
    def elder_report() -> str:
        user_input = request.form.get("user_input", "").strip()
        state = _get_or_create_state()
        resident = _selected_resident()
        if user_input and resident is None:
            return render_template(
                "elder.html",
                **_build_elder_view_model(
                    state,
                    identity_error="请先告诉我您是哪位，这样护理员才能知道要去看谁。",
                    draft_report=user_input,
                    identity_choice="new",
                ),
            )
        if user_input:
            state, _output = run_pipeline(state.session_id, user_input, state)
            save_session(state)
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
        return render_template("admin.html", **_build_admin_view_model())

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


def _build_elder_view_model(
    state: CaseState,
    identity_error: str = "",
    draft_report: str = "",
    identity_choice: str = "",
    identity_name: str = "",
    identity_room: str = "",
) -> dict[str, Any]:
    get_demo_resident()
    return {
        "messages": [message.model_dump() for message in state.conversation_history],
        "assistant_output": state.user_message,
        "needs_follow_up": state.needs_follow_up_question,
        "residents": list_residents(),
        "selected_resident": _selected_resident(),
        "identity_error": identity_error,
        "draft_report": draft_report,
        "identity_choice": identity_choice,
        "identity_name": identity_name,
        "identity_room": identity_room,
    }


def _build_product_view_model() -> dict[str, Any]:
    resident = _product_resident()
    return {
        "resident": resident,
        "latest_event": get_latest_event_for_resident(resident.resident_id),
    }


def _build_admin_view_model() -> dict[str, Any]:
    resident = _product_resident()
    events = list_events_for_resident(resident.resident_id)
    latest_event = events[0] if events else None
    today = datetime.now(CHINA_TIMEZONE).date()
    pending_count = sum(event.staff_status.value == "pending_confirmation" for event in events)
    handled_count = len(events) - pending_count
    family_ready_count = sum(
        event.family_report_ready and event.staff_status.value != "family_contacted"
        for event in events
    )

    return {
        "resident": resident,
        "latest_event": _event_view_model(latest_event) if latest_event else None,
        "summary": {
            "today": sum(_event_local_date(event.created_at) == today for event in events),
            "pending": pending_count,
            "handled": handled_count,
            "family_ready": family_ready_count,
        },
    }


def _event_view_model(event: CareEvent) -> dict[str, Any]:
    status = event.staff_status.value
    return {
        "raw_report": event.raw_report,
        "created_at": _as_china_datetime(event.created_at).strftime("%Y年%m月%d日 %H:%M"),
        "staff_status": STAFF_STATUS_LABELS[status],
        "needs_staff_confirmation": "是" if status == "pending_confirmation" else "否",
        "family_report_status": _family_report_status(event),
        "staff_note": event.staff_note,
    }


def _event_local_date(created_at: datetime):
    return _as_china_datetime(created_at).date()


def _as_china_datetime(created_at: datetime) -> datetime:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at.astimezone(CHINA_TIMEZONE)


def _family_report_status(event: CareEvent) -> str:
    if event.staff_status.value == "family_contacted":
        return "已生成"
    if event.family_report_ready:
        return "可生成"
    return "待护理确认"


def _resolve_resident_selection() -> tuple[Resident | None, str]:
    choice = request.form.get("resident_choice", "").strip()
    if choice == "new":
        name = request.form.get("resident_name", "").strip()
        room = request.form.get("resident_room", "").strip()
        if not name:
            return None, "请告诉我您的姓名。"
        get_demo_resident()
        resident = find_resident_by_exact_name(name)
        return resident or create_resident(name=name, room=room), ""

    resident = get_resident(choice) if choice else None
    if resident is None:
        return None, "请选择或填写您的姓名。"
    return resident, ""


def _select_resident(resident: Resident | None) -> None:
    if resident is None:
        return
    previous_resident_id = session.get(RESIDENT_KEY)
    session[RESIDENT_KEY] = resident.resident_id
    if previous_resident_id != resident.resident_id:
        _delete_current_case_session()


def _selected_resident() -> Resident | None:
    resident_id = session.get(RESIDENT_KEY)
    return get_resident(resident_id) if resident_id else None


def _product_resident() -> Resident:
    return _selected_resident() or get_demo_resident()


def _delete_current_case_session() -> None:
    session_id = session.get(SESSION_KEY)
    if session_id:
        delete_session(session_id)
    session.pop(SESSION_KEY, None)
