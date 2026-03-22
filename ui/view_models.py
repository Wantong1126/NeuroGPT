# UI view models
from __future__ import annotations
from pydantic import BaseModel
class UserInput(BaseModel):
    message: str
    session_id: str
class UIOutput(BaseModel):
    session_id: str
    concern_level: str
    action_level: str
    user_message: str
    caregiver_summary: str | None = None
    follow_up_question: str | None = None
    needs_follow_up: bool
    disclaimer: str | None = None
