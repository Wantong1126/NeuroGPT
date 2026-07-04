# SPDX-License-Identifier: MIT
"""Flask product shell for NeuroGPT v1."""
from __future__ import annotations

import os
import logging
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
    get_identity_residents,
    get_latest_event_for_resident,
    get_resident,
    list_all_events,
    list_events_for_resident,
    update_event_staff_status,
)
from core.session import create_session, delete_session, load_session, save_session
from core.types import CaseState
from modules.elder_observation_response_renderer import render_elder_observation_response
from pipeline.orchestrator import run_pipeline

SESSION_KEY = "neurogpt_session_id"
RESIDENT_KEY = "neurogpt_resident_id"
IDENTITY_NOTICE_KEY = "neurogpt_identity_notice"
CHINA_TIMEZONE = timezone(timedelta(hours=8))
SAFE_ELDER_FALLBACK = "我已经帮您记录下来了，会提醒护理员查看。请您先告诉护理员您现在是否还很不舒服。"
logger = logging.getLogger(__name__)

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
        if (
            request.form.get("resident_choice", "").strip() == "new"
            and not request.form.get("resident_name", "").strip()
            and request.form.get("identity_step") != "name"
        ):
            state = _get_or_create_state()
            return render_template(
                "elder.html",
                **_build_elder_view_model(state, identity_choice="new"),
            )
        resident, error, entered_new_name = _resolve_resident_selection()
        if error:
            state = _get_or_create_state()
            return render_template(
                "elder.html",
                **_build_elder_view_model(
                    state,
                    identity_error=error,
                    identity_choice=request.form.get("resident_choice", ""),
                    identity_name=request.form.get("resident_name", ""),
                ),
            )
        _select_resident(resident)
        if entered_new_name:
            session[IDENTITY_NOTICE_KEY] = "好的，已记录您的姓名。接下来请告诉我哪里不舒服，或者有什么想告诉护理员/家人。"
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
                ),
            )
        if user_input:
            state = process_elder_report_turn(state, resident.resident_id, user_input)
        return render_template("elder.html", **_build_elder_view_model(state))

    @app.get("/staff")
    def staff() -> str:
        return render_template("staff.html", **_build_product_view_model())

    @app.post("/staff/events/<event_id>/update")
    def staff_update_event(event_id: str) -> Any:
        status = request.form.get("staff_status", "").strip()
        note = request.form.get("staff_note", "").strip()
        if status in STAFF_STATUS_LABELS:
            updated = update_event_staff_status(event_id, status, staff_note=note)
            if updated is not None:
                resident = get_resident(updated.resident_id)
                if resident is not None:
                    session[RESIDENT_KEY] = resident.resident_id
        return redirect(url_for("staff"))

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


def process_elder_report_turn(
    state: CaseState,
    resident_id: str,
    user_input: str,
) -> CaseState:
    """Process and persist one elder turn through the active-observation workflow."""
    used_workflow = "active_observation"
    original_turn_count = state.turn_count
    try:
        state, _output = run_pipeline(state.session_id, user_input, state)
        if not state.active_observation:
            raise ValueError("pipeline did not produce an active observation")

        next_question = _active_workflow_question(state)
        if state.action_level.value in {"emergency_now", "same_day_review"}:
            response_mode = "urgent"
        elif not next_question:
            response_mode = "complete"
        elif state.active_observation.get("answer_history"):
            response_mode = "merge"
        else:
            response_mode = "initial"

        elder_response = render_elder_observation_response(
            state.active_observation,
            user_input,
            next_question,
            state.action_level.value,
            response_mode,
        )
    except Exception:
        used_workflow = "legacy_pipeline"
        elder_response = SAFE_ELDER_FALLBACK
        if state.turn_count == original_turn_count:
            state.add_user_message(user_input)

    state.elder_display_response = elder_response
    state.user_message = elder_response
    state.observation_extraction["elder_display_response"] = elder_response
    _replace_latest_assistant_message(state, elder_response)
    save_session(state)
    create_care_event_from_state(state, resident_id, user_input)

    active = state.active_observation
    logger.info(
        "route=elder/report used_workflow=%s pending_field=%s specific_problem=%s "
        "body_location=%s sensation_quality=%s elder_display_response=%s",
        used_workflow,
        state.pending_field,
        active.get("specific_problem", ""),
        active.get("body_location", ""),
        active.get("sensation_quality", ""),
        elder_response[:80],
    )
    return state


def _active_workflow_question(state: CaseState) -> str | None:
    question = state.pending_question or state.follow_up_question
    if not question:
        return None
    legacy_generic = (
        "更像是麻木、没力、动作不灵活，还是感觉变迟钝" in question
        or all(term in question for term in ("麻木", "没力", "动作不灵活", "感觉迟钝"))
    )
    if not legacy_generic:
        return question

    planned = str(state.active_observation.get("next_best_question") or "").strip()
    if planned and not all(term in planned for term in ("麻木", "没力", "动作不灵活", "感觉迟钝")):
        question = planned
    else:
        question = "这个情况是今天刚出现的吗？现在有没有比刚开始更严重？"
    state.follow_up_question = question
    if state.pending_question:
        state.pending_question = question
    return question


def _replace_latest_assistant_message(state: CaseState, response: str) -> None:
    if state.conversation_history and state.conversation_history[-1].role == "assistant":
        state.conversation_history[-1].content = response
    else:
        state.add_assistant_message(response)


def _build_elder_view_model(
    state: CaseState,
    identity_error: str = "",
    draft_report: str = "",
    identity_choice: str = "",
    identity_name: str = "",
) -> dict[str, Any]:
    residents = get_identity_residents()
    selected_resident = _selected_resident()
    if selected_resident and all(item.resident_id != selected_resident.resident_id for item in residents):
        residents.append(selected_resident)
    return {
        "messages": [
            message.model_dump()
            for message in state.conversation_history
            if message.role == "user"
        ],
        "elder_display_response": state.elder_display_response,
        "needs_follow_up": state.needs_follow_up_question,
        "residents": residents,
        "selected_resident": selected_resident,
        "identity_error": identity_error,
        "identity_notice": session.pop(IDENTITY_NOTICE_KEY, ""),
        "draft_report": draft_report,
        "identity_choice": identity_choice,
        "identity_name": identity_name,
    }


def _build_product_view_model() -> dict[str, Any]:
    resident = _product_resident()
    latest_event = get_latest_event_for_resident(resident.resident_id)
    extraction = latest_event.observation_extraction if latest_event else {}
    observations = extraction.get("observations") or []
    return {
        "resident": resident,
        "latest_event": latest_event,
        "observation": observations[0] if observations else None,
        "recommended_staff_handoff": extraction.get("recommended_staff_handoff", ""),
        "confirmed_family_summary": extraction.get(
            "recommended_family_summary_after_confirmation",
            "",
        ),
        "staff_status_label": STAFF_STATUS_LABELS.get(
            latest_event.staff_status.value,
            "待护理员确认",
        ) if latest_event else "",
        "family_follow_up_label": _family_follow_up_label(latest_event) if latest_event else "",
    }


def _build_admin_view_model() -> dict[str, Any]:
    resident = _product_resident()
    events = list_all_events()
    today = datetime.now(CHINA_TIMEZONE).date()
    pending_count = sum(event.staff_status.value == "pending_confirmation" for event in events)
    handled_count = len(events) - pending_count
    family_ready_count = sum(
        event.family_report_ready and event.staff_status.value != "family_contacted"
        for event in events
    )

    return {
        "resident": resident,
        "event_rows": [_institution_event_view_model(event) for event in events],
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


def _institution_event_view_model(event: CareEvent) -> dict[str, Any]:
    resident = get_resident(event.resident_id)
    observations = event.observation_extraction.get("observations") or []
    observation = observations[0] if observations else {}
    return {
        "resident_name": resident.name if resident else "未知老人",
        "room": resident.room if resident and resident.room else "未填写",
        "raw_quote": observation.get("raw_quote") or event.raw_report,
        "specific_problem": observation.get("specific_problem") or event.raw_report,
        "staff_status": STAFF_STATUS_LABELS.get(event.staff_status.value, "待护理员确认"),
        "staff_note": event.staff_note or "暂无",
        "family_report_status": _family_report_status(event),
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


def _family_follow_up_label(event: CareEvent) -> str:
    if event.staff_status.value == "family_contacted":
        return "已处理并已联系家属"
    if event.staff_status.value == "confirmed":
        return "已处理，将继续关注"
    if event.staff_status.value == "monitoring":
        return "将继续关注"
    if event.staff_status.value == "offline_handled":
        return "已线下处理"
    return "等待护理员确认"


def _resolve_resident_selection() -> tuple[Resident | None, str, bool]:
    choice = request.form.get("resident_choice", "").strip()
    if choice == "new":
        name = request.form.get("resident_name", "").strip()
        if not name:
            return None, "请填写您的姓名。", True
        get_identity_residents()
        resident = find_resident_by_exact_name(name)
        return resident or create_resident(name=name), "", True

    resident = get_resident(choice) if choice else None
    if resident is None:
        return None, "请先选择您的姓名。", False
    return resident, "", False


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
