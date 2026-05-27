# SPDX-License-Identifier: MIT
"""Local/demo HTTP API for the MVP response contract."""
from __future__ import annotations

from uuid import uuid4

from flask import Flask, jsonify, request
from pydantic import BaseModel, Field, ValidationError, field_validator

from core.types import CaseState, MVPResponsePayload
from pipeline.orchestrator import run_pipeline, to_mvp_response_payload


SESSION_STATES: dict[str, CaseState] = {}


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message must not be blank")
        return cleaned


class ChatResponse(BaseModel):
    session_id: str
    payload: MVPResponsePayload


class ResetRequest(BaseModel):
    session_id: str | None = None


def create_app() -> Flask:
    app = Flask(__name__)

    @app.post("/api/chat")
    def chat():
        try:
            chat_request = ChatRequest(**(request.get_json(silent=True) or {}))
        except ValidationError as exc:
            return jsonify({"error": "invalid_request", "details": _json_safe_errors(exc)}), 400

        session_id = chat_request.session_id or _new_session_id()
        state = SESSION_STATES.get(session_id)
        state, output = run_pipeline(session_id, chat_request.message, state)
        SESSION_STATES[session_id] = state

        response = ChatResponse(
            session_id=session_id,
            payload=to_mvp_response_payload(state, output),
        )
        return jsonify(response.model_dump(mode="json"))

    @app.post("/api/reset")
    def reset():
        try:
            reset_request = ResetRequest(**(request.get_json(silent=True) or {}))
        except ValidationError as exc:
            return jsonify({"error": "invalid_request", "details": _json_safe_errors(exc)}), 400

        if reset_request.session_id:
            removed = SESSION_STATES.pop(reset_request.session_id, None) is not None
            return jsonify({"reset": removed, "session_id": reset_request.session_id})

        SESSION_STATES.clear()
        return jsonify({"reset": True, "session_id": None})

    return app


def _new_session_id() -> str:
    return f"api_{uuid4().hex}"


def _json_safe_errors(exc: ValidationError) -> list[dict]:
    return [
        {key: value for key, value in error.items() if key != "ctx"}
        for error in exc.errors()
    ]


app = create_app()
