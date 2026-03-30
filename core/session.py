# SPDX-License-Identifier: MIT
"""File-backed session storage for persisted CaseState."""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from core.types import CaseState
from pipeline.state import new_case

SESSIONS_DIR = Path(__file__).parent.parent / ".sessions"



def _session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"



def create_session(session_id: str | None = None) -> CaseState:
    if session_id is None:
        session_id = f"s_{int(time.time() * 1000)}_{uuid4().hex[:8]}"

    existing = load_session(session_id)
    if existing is not None:
        return existing

    state = new_case(session_id=session_id)
    save_session(state)
    return state



def save_session(state: CaseState) -> None:
    SESSIONS_DIR.mkdir(exist_ok=True)
    data = state.model_dump(mode="json")
    for message in data.get("conversation_history", []):
        if message.get("timestamp") is not None:
            message["timestamp"] = str(message["timestamp"])
    _session_path(state.session_id).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )



def load_session(session_id: str) -> CaseState | None:
    path = _session_path(session_id)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        for message in data.get("conversation_history", []):
            timestamp = message.get("timestamp")
            if isinstance(timestamp, str) and timestamp:
                message["timestamp"] = datetime.fromisoformat(timestamp)
        return CaseState(**data)
    except Exception:
        return None



def list_sessions() -> list[str]:
    if not SESSIONS_DIR.exists():
        return []
    return sorted(path.stem for path in SESSIONS_DIR.glob("*.json"))



def delete_session(session_id: str) -> bool:
    path = _session_path(session_id)
    if not path.exists():
        return False
    path.unlink()
    return True
