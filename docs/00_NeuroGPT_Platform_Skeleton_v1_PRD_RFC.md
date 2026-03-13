# NeuroGPT — Platform Skeleton (v1) — PRD + RFC
**Master Kickoff Prompt for Coding Agent (Claude Code / VS Code)**

IMPORTANT:
- Use this entire document as the **FIRST** prompt to the coding agent.
- Do **not** write implementation code until the “Final Instruction” section is satisfied.

---

## 📘 Product Requirements Document (PRD)

### Product Name
NeuroGPT (working name)

### Product Goal
Build a **mode-based** conversational AI platform (cloud-hosted, text-only) that can safely host multiple specialized assistants (“modes”) under one shared platform:
- **Mode A (Medical Neuro-Health for older adults/caregivers)** — safety-first triage + explanations
- **Mode B (Identity, Relationships, Urban Wellbeing — Lite)** — structured reflective dialogue (archived/deprecated in this repo)
- **Mode C (Women’s cycle/hormone wellbeing + medical safety)** — future mode (not implemented in v1)

This platform prioritizes **safety, clarity, and timing** over clinical authority or completeness.

### Target Users
- Builders (non-professional) who need a safe, auditable architecture
- End users vary by mode (defined in each mode PRD)

### Deployment Decision (Locked)
- Cloud-hosted deployment
- GPU-backed inference (model-agnostic)
- Designed so the system can later scale to multiple users

### Memory Policy (Locked for v1)
Short-term memory only:
- rolling conversation summary
- plus last few turns (e.g., last 5 turns)
Hard caps on:
- maximum context length
- maximum input length per turn
No permanent storage of medical history in v1.
No long-term memory across sessions in v1.

### Disclaimer Policy (Locked)
Explicit disclaimers are mandatory.
Disclaimers must be:
- configurable
- documented
- easily modifiable later
Disclaimers must **not** be hard-coded into model prompts.

### Language & Localization (Configurable)
- Output language is governed by a **language policy layer** (configuration).
- Default for this repo: **English output** unless user switches.
- Retrieval corpora may be English while output can be English or Chinese (translation must be faithful; do not invent).

---

## ✅ v1 Platform Build Scope (Very Important)

### You build (v1)
- A **router**
- A **mode interface contract**
- A **safety hook**
- A **memory hook**
- **config loading**
- **prompt loading**
- minimal logging/observability (triage/safety decisions, mode selection)

### You do NOT build (v1 platform skeleton)
- full medical pipelines (implemented only when building Mode A)
- full RAG (implemented only by modes that require it)
- long-term storage
- advanced evaluation tooling

---

## 📐 Request for Comments (RFC): System Architecture

### Mode-Based Cognitive Architecture (Platform Layer)
NeuroGPT is implemented as a **single platform** with multiple operational modes.

Each mode defines:
- Domain scope
- Safety policy tier
- Knowledge access level (**K0 none / K1 limited / K2 full RAG**)
- Prompt templates
- Output constraints

Modes are routed explicitly at session start (or via a simple router).

### Knowledge Access Levels
- **K0**: No retrieval. Structured dialogue only (templates/scaffolds).
- **K1**: Lightweight retrieval (curated, non-medical or low-risk).
- **K2**: Full retrieval with strong grounding, abstention rules, and safety constraints (medical grade).

### High-Level Architecture (Platform View)
User Input
↓
**Mode Router (Platform)**
↓
Mode-specific pipeline (varies per mode)
↓
LLM (conversation step, constrained by mode policy)
↓
Memory update (summary + last turns)
↓
Logging

### Platform Component Responsibilities
1. **Mode Router**
   - Decide which mode handles the session (explicit user choice preferred; otherwise default).
2. **Mode Contract (Interface)**
   - Every mode must implement the same interface:
     - `step(user_input, state) -> response`
     - `summarize(session) -> summary`
     - `safety_check(user_input) -> {ok|escalate}`
3. **Safety Hook**
   - Runs before the mode produces a normal response.
   - Deterministic, conservative, auditable.
4. **Memory Hook**
   - Updates rolling summary + last N turns.
5. **Config Loader**
   - Loads language policy, disclaimers, mode enablement, thresholds.
6. **Prompt Loader**
   - Loads prompts/templates per mode from files (not hard-coded).

### Development Principles (for a Non-Professional Builder)
- Prefer simple, explicit rules over clever behavior.
- Make each stage observable and testable.
- Log:
  - mode selection
  - safety triggers
  - escalation overrides (if any)
- Favor readability over performance optimization.
- Build incrementally:
  - safety first
  - features later

---

## 🔗 Connection to Implementation Steps (Platform Skeleton Only)
Do not proceed to later steps until each earlier step is understood and validated.

1. Create repo scaffold + folder structure
2. Implement mode interface contract + mode registry
3. Implement router (explicit selection + default)
4. Implement config loader + prompt loader
5. Implement safety hook (generic interface; mode-specific rules live in modes)
6. Implement memory hook (summary + last turns)
7. Add minimal CLI/demo runner to exercise one mode (do not use archived Mode B as the example)

---

## 🛑 Final Instruction to the Coding Agent
Do NOT write production code yet.

First, you must:
1. Confirm understanding of this platform PRD + RFC
2. Restate the platform architecture in your own words
3. Identify potential safety failure modes (platform-level)
4. Propose how each failure mode is mitigated

Only proceed to implementation after explicit confirmation.
