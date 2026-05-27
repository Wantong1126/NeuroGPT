# NeuroGPT MVP Response Contract

This contract defines the backend payload a future web or mobile UI can render without inspecting internal pipeline objects. It is not a UI implementation and does not add audience mode.

Use `pipeline.orchestrator.to_mvp_response_payload(state, output)` after `run_pipeline(...)`.

## Frontend-Facing Fields

- `user_message`: elder-facing response text. This is safe to show to the elder user.
- `action_level`: deterministic action tier, such as `emergency_now`, `same_day_review`, `prompt_clinical_review`, or `monitor`.
- `concern_level`: deterministic concern level used by the response.
- `next_action_label`: short display label for the next action.
- `needs_follow_up_question`: whether the UI should show a single clarification question.
- `follow_up_question`: the one clarification question, when present.
- `caregiver_summary`: concise caregiver/doctor handoff text.
- `disclaimer`: configured disclaimer text, when present.
- `guidance_snippets`: short source-backed guidance snippets. These are displayable, but should remain secondary to the action instruction.

## Internal/Debug Metadata

The `debug_metadata` object is for developer tools, QA screens, logs, or support workflows. Do not show it in normal elder-facing UI.

- `llm_observation_status`
- `observation_mode_used`
- `llm_observation_error_type`
- `deterministic_observation_count`
- `llm_observation_count`

These fields help verify whether deterministic-only extraction, LLM augmentation, or deterministic fallback was used.

## What Not To Show Elder Users

Normal user-facing UI should not show provider names, API status, timeout text, JSON parsing details, DeepSeek status, fallback mode, or raw LLM metadata. These details belong in `debug_metadata`, not `user_message`.

## Caregiver Summary

The caregiver summary should be displayed as a short handoff, separate from the elder-facing message. It should preserve observed signs, timing when available, escalation rationale when present, and the recommended next action. It should not claim a diagnosis.

## Audience Mode

Audience mode is intentionally deferred until UI/onboarding exists. The current contract exposes both elder-facing text and caregiver handoff text so a future interface can decide where and when to show each piece.

## Demo Runner

Run deterministic demo payloads without live API keys:

```powershell
python scripts\demo_mvp_flows.py
```

The demo covers emergency red flags, ambiguous sensory complaints, mild transient symptoms, chronic memory decline, LLM failure fallback, and mocked LLM success augmentation.
