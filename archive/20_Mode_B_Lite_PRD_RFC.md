# NeuroGPT — Mode B (Identity, Relationships, Urban Wellbeing — Lite) — PRD + RFC
**Kickoff Prompt for Coding Agent (Claude Code / VS Code)**

IMPORTANT:
- Use **Platform Skeleton (v1)** document first.
- Then paste this document to implement **Mode B v1** on top of the platform.

---

## 📘 PRD (Mode B v1)

### Purpose
Support identity formation, relational skills, autonomy, and wellbeing in students and young adults.

### Non-goals (Out of Scope)
- Diagnosis
- Therapy
- Crisis intervention beyond referral

### Core Interaction Pattern
Structured reflective dialogue using predefined conversational scaffolds.

### Knowledge Access
**K0 (no retrieval)** in v1 (rapid deployment).

### Safety Tier
Psychological-risk detection with immediate escalation to support resources.

### Forward Compatibility Guarantee
Mode B v1 is intentionally implemented without retrieval to enable rapid deployment.
The architecture guarantees forward compatibility with richer knowledge access, tools, and long-term memory without breaking existing prompts or safety guarantees.

---

## 📐 RFC (Mode B v1 Architecture)

### Mode Definition
- **Mode Name:** B
- **Domain Scope:** identity development, relationships, autonomy, urban wellbeing
- **Knowledge Access:** **K0**
- **Safety Tier:** psych risk detection + referral
- **Output Constraints:** no diagnosis; no therapy claims; warm but non-authoritative

### Sub-modes (must exist in v1)
1. Identity & values clarification
2. Relationships & boundaries
3. Urban loneliness & social action planning

### Universal 6-Step Scaffold (applied to all sub-modes)
1. Clarify situation (2–3 sentences)
2. Name emotions (offer simple options)
3. Identify needs/values (belonging, respect, autonomy, meaning, safety, etc.)
4. Identify obstacles (fear of conflict, shame, time, uncertainty)
5. Offer two paths:
   - A: short-term relief (today)
   - B: long-term build (7-day plan)
6. Summarize + next step (user chooses 1 smallest action)

### Safety Handling (Mode B)
- If high-risk psychological signals detected (self-harm ideation, abuse threats, loss of control):
  - Immediately switch to crisis referral template
  - Do not diagnose, promise confidentiality, or provide dangerous instructions
  - Encourage reaching a trusted person and local emergency/mental health supports

### Memory (Mode B)
- Use platform short-term memory hook.
- End of session generates a structured summary:
  - key concerns
  - values mentioned
  - current goals
  - emotional tone
- Next session injects summary.

---

## 🔗 Implementation Order (Mode B v1)
1. Implement Mode B registration in mode registry + router selection
2. Create external prompt/templates for the 3 sub-modes
3. Implement the 6-step scaffold engine
4. Implement Mode B safety detection + crisis templates (config-driven)
5. Implement session summary schema + injection
6. Add demo prompts (10 per sub-mode) + a CLI runner to test

---

## 🛑 Final Instruction to the Coding Agent
Do NOT write production code yet.

First, you must:
1. Confirm understanding of Mode B v1 scope (K0, no retrieval)
2. Restate how the 3 sub-modes and 6-step scaffold work
3. Identify Mode B safety failure modes (psych risk)
4. Propose mitigations (conservative triggers + referral templates)

Only proceed to implementation after explicit confirmation.
