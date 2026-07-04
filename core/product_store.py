# SPDX-License-Identifier: MIT
"""File-backed product records for the NeuroGPT v1 care workflow."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from core.types import CaseState

PRODUCT_DATA_DIR = Path(__file__).parent.parent / ".product_data"
DEMO_RESIDENT_ID = "resident_demo_wang_xiulan"
IDENTITY_RESIDENT_SEEDS = (
    ("resident_demo_li_guoqiang", "李国强"),
    ("resident_demo_zhang_mingde", "张明德"),
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class CareEventSource(str, Enum):
    ELDER = "elder"
    STAFF = "staff"
    FAMILY = "family"


class StaffStatus(str, Enum):
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    MONITORING = "monitoring"
    FAMILY_CONTACTED = "family_contacted"
    OFFLINE_HANDLED = "offline_handled"


class Resident(BaseModel):
    resident_id: str
    name: str
    age: int | None = None
    gender: str = ""
    room: str = ""
    institution_name: str = "示例养老院"
    family_contact_name: str = ""
    family_relationship: str = ""
    care_focus: list[str] = Field(default_factory=list)


class CareEvent(BaseModel):
    event_id: str
    resident_id: str
    source: CareEventSource
    raw_report: str
    created_at: datetime
    case_session_id: str
    action_level: str
    concern_level: str
    needs_follow_up: bool
    follow_up_question: str | None = None
    staff_status: StaffStatus = StaffStatus.PENDING_CONFIRMATION
    staff_note: str = ""
    caregiver_summary: str = ""
    family_report_ready: bool = False
    observation_extraction: dict[str, Any] = Field(default_factory=dict)


def get_demo_resident() -> Resident:
    """Return the seeded demo resident, creating its record when needed."""
    path = _record_path(_residents_dir(), DEMO_RESIDENT_ID)
    if path.exists():
        resident = Resident.model_validate_json(path.read_text(encoding="utf-8"))
        if resident.family_relationship == "家属":
            resident.family_relationship = "女儿"
            _write_record(path, resident)
        return resident

    resident = Resident(
        resident_id=DEMO_RESIDENT_ID,
        name="王秀兰",
        age=82,
        gender="女",
        room="203床",
        institution_name="示例养老院",
        family_contact_name="王女士",
        family_relationship="女儿",
        care_focus=["睡眠", "记忆", "行动变化"],
    )
    _write_record(path, resident)
    return resident


def get_identity_residents() -> list[Resident]:
    """Return the fixed MVP residents offered on the elder identity screen."""
    residents = [get_demo_resident()]
    for resident_id, name in IDENTITY_RESIDENT_SEEDS:
        resident = get_resident(resident_id)
        if resident is None:
            resident = Resident(resident_id=resident_id, name=name)
            _write_record(_record_path(_residents_dir(), resident_id), resident)
        residents.append(resident)
    return residents


def get_resident(resident_id: str) -> Resident | None:
    """Load one resident by ID."""
    try:
        path = _record_path(_residents_dir(), resident_id)
    except ValueError:
        return None
    if not path.exists():
        return None
    try:
        return Resident.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def list_residents() -> list[Resident]:
    """Return all stored residents ordered by name and ID."""
    directory = _residents_dir()
    if not directory.exists():
        return []

    residents: list[Resident] = []
    for path in directory.glob("*.json"):
        try:
            residents.append(Resident.model_validate_json(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return sorted(residents, key=lambda resident: (resident.name, resident.resident_id))


def find_resident_by_exact_name(name: str) -> Resident | None:
    """Find a resident by exact trimmed name match."""
    expected_name = name.strip()
    if not expected_name:
        return None
    return next((resident for resident in list_residents() if resident.name == expected_name), None)


def create_resident(
    name: str,
    room: str = "",
    institution_name: str = "示例养老院",
) -> Resident:
    """Create the minimal resident record supported by the MVP identity flow."""
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("resident name is required")
    resident = Resident(
        resident_id=f"resident_{uuid4().hex}",
        name=clean_name,
        room=room.strip(),
        institution_name=institution_name.strip() or "示例养老院",
    )
    _write_record(_record_path(_residents_dir(), resident.resident_id), resident)
    return resident


def create_care_event_from_state(
    state: CaseState,
    resident_id: str,
    raw_report: str,
    source: CareEventSource | str = CareEventSource.ELDER,
) -> CareEvent:
    """Persist a care event snapshot, updating an active multi-turn observation."""
    _validate_id(resident_id)
    event_source = CareEventSource(source)
    original_report = state.active_observation.get("raw_quote") or raw_report
    if state.active_observation:
        existing = next(
            (
                event
                for event in list_events_for_resident(resident_id)
                if event.case_session_id == state.session_id
                and event.source == event_source
                and event.raw_report == original_report
                and event.staff_status == StaffStatus.PENDING_CONFIRMATION
            ),
            None,
        )
        if existing is not None:
            existing.action_level = state.action_level.value
            existing.concern_level = state.concern_level.value
            existing.needs_follow_up = state.needs_follow_up_question
            existing.follow_up_question = state.follow_up_question
            existing.caregiver_summary = state.caregiver_summary or ""
            existing.observation_extraction = state.observation_extraction
            _write_record(_record_path(_events_dir(), existing.event_id), existing)
            return existing

    event = CareEvent(
        event_id=f"event_{uuid4().hex}",
        resident_id=resident_id,
        source=event_source,
        raw_report=original_report,
        created_at=datetime.now(timezone.utc),
        case_session_id=state.session_id,
        action_level=state.action_level.value,
        concern_level=state.concern_level.value,
        needs_follow_up=state.needs_follow_up_question,
        follow_up_question=state.follow_up_question,
        caregiver_summary=state.caregiver_summary or "",
        observation_extraction=state.observation_extraction,
    )
    _write_record(_record_path(_events_dir(), event.event_id), event)
    return event


def list_events_for_resident(resident_id: str) -> list[CareEvent]:
    """Return a resident's care events ordered newest first."""
    _validate_id(resident_id)
    directory = _events_dir()
    if not directory.exists():
        return []

    events: list[CareEvent] = []
    for path in directory.glob("*.json"):
        try:
            event = CareEvent.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if event.resident_id == resident_id:
            events.append(event)
    return sorted(events, key=lambda event: (event.created_at, event.event_id), reverse=True)


def list_all_events() -> list[CareEvent]:
    """Return all care events ordered newest first."""
    directory = _events_dir()
    if not directory.exists():
        return []
    events: list[CareEvent] = []
    for path in directory.glob("*.json"):
        try:
            events.append(CareEvent.model_validate_json(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return sorted(events, key=lambda event: (event.created_at, event.event_id), reverse=True)


def get_latest_event_for_resident(resident_id: str) -> CareEvent | None:
    events = list_events_for_resident(resident_id)
    return events[0] if events else None


def update_event_staff_status(
    event_id: str,
    staff_status: StaffStatus | str,
    staff_note: str | None = None,
    family_report_ready: bool | None = None,
) -> CareEvent | None:
    """Update staff workflow fields and return the saved event, if found."""
    path = _record_path(_events_dir(), event_id)
    if not path.exists():
        return None

    event = CareEvent.model_validate_json(path.read_text(encoding="utf-8"))
    status = StaffStatus(staff_status)
    event.staff_status = status
    if staff_note is not None:
        event.staff_note = staff_note
    if family_report_ready is not None:
        event.family_report_ready = family_report_ready
    elif status in {StaffStatus.CONFIRMED, StaffStatus.FAMILY_CONTACTED}:
        event.family_report_ready = True
    _write_record(path, event)
    return event


def _residents_dir() -> Path:
    return PRODUCT_DATA_DIR / "residents"


def _events_dir() -> Path:
    return PRODUCT_DATA_DIR / "care_events"


def _record_path(directory: Path, record_id: str) -> Path:
    _validate_id(record_id)
    return directory / f"{record_id}.json"


def _validate_id(record_id: str) -> None:
    if not record_id or not _SAFE_ID.fullmatch(record_id):
        raise ValueError("record IDs may contain only letters, numbers, underscores, and hyphens")


def _write_record(path: Path, record: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary_path.write_text(
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(path)
