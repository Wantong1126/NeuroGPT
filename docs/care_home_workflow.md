# NeuroGPT Care-Home Workflow Contract

This workflow targets the room-tablet scenario: an older resident reports physical, neurological, cognitive, or psychological wellbeing changes from a care-home room, and staff need a structured handoff without asking the resident to repeat everything.

This is not a diagnosis system. NeuroGPT keeps risk rules and action tiers as the authority. The care-home fields organize already-computed pipeline state for staff review.

## Payload Objects

`care_home_handoff` is a staff handoff for the current conversation turn:

- `resident_summary`: short resident-facing report summary.
- `known_facts`: structured facts already understood from observations, timing, and laterality.
- `missing_critical_info`: important details staff should confirm.
- `risk_status`: current concern/action status.
- `escalation_reason`: red-flag rationale when escalation is already indicated.
- `recommended_staff_action`: operational next step for care-home staff.
- `follow_up_tasks`: conservative checks staff can perform or document.
- `suggested_next_observations`: fields useful for bedside reassessment.
- `caregiver_brief`: concise handoff text derived from existing caregiver summary.

`daily_report_item` is a single review item for future department aggregation:

- `headline`
- `category`
- `risk_level`
- `action_level`
- `summary_for_department`
- `unresolved_questions`
- `staff_follow_up_needed`
- `escalation_needed`

Categories currently supported by contract are `neuro_symptom`, `cognitive_change`, `psychological_wellbeing`, `fall_or_injury`, and `general_monitoring`.

## Generation Rules

The handoff and daily report are built deterministically from `CaseState`, `PipelineOutput`, existing observations, red flags, follow-up question, caregiver summary, concern level, and action level.

No LLM call, RAG, external retrieval, database lookup, or new medical decision is added. The fields explain and organize the current state; they do not decide care level.

## Staff Use

Staff can use the handoff to answer:

- What did the resident report?
- What is already known?
- What is still missing?
- What should be checked next?
- Does this need escalation now?
- What should go into the daily department review?

For high-risk cases, staff tasks emphasize onset time, duration, whether symptoms are ongoing, focal neurological checks, fall/head-injury checks, and baseline difference. For monitor or ambiguous cases, tasks emphasize persistence, worsening, functional impact, new red flags, and baseline difference.

## Future Work

This contract does not add resident persistence or department dashboards yet. Future work should add:

- `resident_id` and `room_id`
- persistent database storage
- daily report aggregator
- staff dashboard
- longitudinal baseline comparison
- controlled LLM response writer
- privacy, audit, retention, and access controls
