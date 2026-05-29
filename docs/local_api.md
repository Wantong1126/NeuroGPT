# Local MVP API And Demo UI

This is a local/demo HTTP API and simple web UI for the NeuroGPT MVP response contract. It is production-compatible in shape, but it is not production infrastructure.

## Run Locally

```powershell
python local_api.py
```

By default the API listens on `127.0.0.1:5050`. You can override:

```powershell
$env:NEUROGPT_API_HOST = "127.0.0.1"
$env:NEUROGPT_API_PORT = "5050"
python local_api.py
```

Open the local demo UI:

```text
http://127.0.0.1:5050/
```

The page calls `POST /api/chat` with browser `fetch`, stores the returned `session_id` in browser memory, and displays the returned `MVPResponsePayload`.

The debug panel is collapsed by default. It is for local development and QA, not normal elder-facing production use.

## Chat Endpoint

`POST /api/chat`

Request:

```json
{
  "session_id": "optional-existing-session",
  "message": "sudden right arm weakness and face droop"
}
```

`session_id` is optional. If omitted, the API creates one. `message` must be a non-empty string.

Response:

```json
{
  "session_id": "api_example",
  "payload": {
    "user_message": "...",
    "action_level": "emergency_now",
    "concern_level": "high",
    "next_action_label": "联系当地急救电话或前往急诊",
    "needs_follow_up_question": false,
    "follow_up_question": null,
    "caregiver_summary": "...",
    "disclaimer": "...",
    "guidance_snippets": ["..."],
    "care_home_handoff": {
      "resident_summary": "...",
      "known_facts": ["..."],
      "missing_critical_info": ["..."],
      "risk_status": "high/emergency_now",
      "escalation_reason": "...",
      "recommended_staff_action": "...",
      "follow_up_tasks": ["..."],
      "suggested_next_observations": ["..."],
      "caregiver_brief": "..."
    },
    "daily_report_item": {
      "headline": "...",
      "category": "neuro_symptom",
      "risk_level": "high",
      "action_level": "emergency_now",
      "summary_for_department": "...",
      "unresolved_questions": ["..."],
      "staff_follow_up_needed": true,
      "escalation_needed": true
    },
    "debug_metadata": {
      "llm_observation_status": "not_configured",
      "observation_mode_used": "deterministic_only",
      "llm_observation_error_type": null,
      "deterministic_observation_count": 2,
      "llm_observation_count": 0
    }
  }
}
```

The frontend may render the top-level `payload` display fields. `care_home_handoff` and `daily_report_item` are for staff/caregiver review workflows. `debug_metadata` is for developer tooling and QA, not normal elder-facing UI.

## Reset Endpoint

`POST /api/reset`

To clear one session:

```json
{
  "session_id": "api_example"
}
```

To clear all local demo sessions, send `{}`.

## Session Behavior

Sessions are stored in memory only. The same `session_id` continues multi-turn state. Restarting the local Python process clears all sessions.

## Local/Demo Only

This API and UI intentionally do not add Docker, HTTPS, authentication, database persistence, admin screens, cloud deployment, user management, or production secret handling.

Before production UI/deployment, add:

- Docker or equivalent release packaging
- HTTPS termination
- persistent session/database storage
- authentication and authorization
- privacy controls and data retention policy
- audit logging
- monitoring and alerting
- rate limits and abuse protection
- secret management
- deployment health checks
- reviewed production UI flows for elder users and caregivers
- resident/room identifiers and persistent care-home daily review aggregation
- accessibility testing across mobile and desktop

The API does not change medical logic. `risk_rules`, action tiers, extraction, provider configuration, LLM prompt, guidance matching, and response wording remain owned by the existing pipeline.
