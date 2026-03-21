# NeuroGPT v2 — Single-Product PRD / RFC
**Status:** Final working product definition for v2
**Supersedes:** All previous multi-mode / platform / Mode B planning documents
**Scope:** This document is the only active product-design and implementation reference for NeuroGPT

---

## 1. Product Decision

NeuroGPT is **not** a multi-mode conversational platform.

NeuroGPT v2 is a **single-purpose digital product** designed to help older adults and their caregivers:

- **Notice** potentially serious neurological symptoms
- **Stop** minimizing or delaying them
- **Understand** why they matter
- **Take** appropriate next-step action

This product is **not** a general medical chatbot, not a companionship bot, and not a broad wellness assistant. Its job is narrow and practical.

---

## 2. Target Users

- **Primary:** Older adults (60+) experiencing or noticing cognitive/physical symptoms
- **Secondary:** Adult children / caregivers of older adults
- **Context:** Often in denial, anxious, or unsure whether symptoms are "normal aging" or serious

---

## 3. Core Problem

Older adults and their families often:
- Dismiss early neurological symptoms as "just aging"
- Delay seeking help due to fear, stigma, or lack of awareness
- Have no accessible, credible tool to assess whether symptoms warrant action
- When they do seek help, struggle to communicate concerns effectively to doctors

---

## 4. Product Vision

A trusted, calm, evidence-based conversational guide that:

1. **Elicits** — helps users describe what they've noticed without medical jargon
2. ** contextualizes** — explains why this symptom matters in plain language
3. **Calibrates urgency** — gives honest, conservative guidance on whether to act now
4. **Prepares** — helps users know what to say and expect at a doctor's visit
5. **Supports caregivers** — gives them language and next steps

---

## 5. Safety & Ethical Boundaries (Non-Negotiable)

- **No diagnosis** — ever. State clearly: "I am not a doctor."
- **No medical advice** beyond general information
- **Conservative escalation** — when in doubt, advise seeking professional care
- **Crisis handling** — immediate, clear referral to emergency services if safety language detected
- **Transparency** — always disclose the AI's nature and limitations
- **Privacy** — no storage of personal health data without explicit consent

---

## 6. Symptoms in Scope (v2)

Focus on early presentation of high-burden neurological conditions in older adults:

| Category | Examples |
|---|---|
| **Cognitive** | Memory lapses, word-finding difficulty, getting lost in familiar places |
| **Motor** | Tremor, slowness, stiffness, falls |
| **Behavioral** | Sleep disturbances, apathy, personality change, hallucinations |
| **vascular** | Sudden confusion, speech difficulty, asymmetric weakness |
| **Functional** | Difficulty with daily activities (driving, managing finances, medication) |

---

## 7. Knowledge Architecture

- **RAG (Retrieval-Augmented Generation)** — grounded in peer-reviewed neurology literature, clinical guidelines, patient education materials
- **Abstention policy** — if query is outside scope or above confidence threshold, say so clearly and refer
- **Language** — output in user's preferred language; knowledge base primarily in English, translated faithfully

---

## 8. User Interaction Model

- Conversational: natural language, not structured forms
- Adaptive: adjusts depth based on user responses
- Memory: short-term only (session-level); no persistent health record storage
- Tone: calm, warm, non-alarmist, non-technical

---

## 9. Disclaimer Requirements

Every response that touches on symptoms or health must include a visible disclaimer:
- Clearly stating NeuroGPT is not a medical professional
- Directing users to seek qualified healthcare providers for diagnosis or treatment decisions

Disclaimers must be:
- Configurable in `configs/disclaimers.yaml`
- Never hard-coded into LLM prompts
- Reviewed and updated by a clinical advisor before going live

---

## 10. Technical Scope for v2

### In Scope
- Conversational RAG engine (symptom elicitation + explanation + guidance)
- Safety hook (crisis detection + escalation)
- Disclaimer injection layer
- Short-term memory (session summary only)
- CLI demo interface
- Basic evaluation: response accuracy, safety boundary adherence

### Out of Scope
- Multi-user accounts / long-term health records
- Integration with electronic health records (EHR)
- Mobile app / web UI (future)
- Any form of diagnosis or treatment recommendation

---

## 11. Success Metrics

- Users complete a symptom conversation and feel more informed, less anxious
- Safety hook correctly escalates all simulated crisis inputs
- Clinically relevant queries receive abstain/refer responses when confidence is low
- Disclaimer is visible and present in >95% of health-related responses (audit)

---

## 12. Open Questions

- [ ] Who is the intended payer / business model? (B2C, B2B to health systems, caregiver subscription?)
- [ ] Is there a clinical advisor attached to this project for disclaimer review?
- [ ] What is the acceptable false-negative rate for safety escalation?
- [ ] Is Chinese-language output required at launch, or English-only?
- [ ] What is the vector database / embedding model preference?
- [ ] What is the deployment target? (cloud-hosted; GPU or CPU inference?)
