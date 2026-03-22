# NeuroGPT v2 — Single-Product PRD / RFC

## 1. Document Status

**Status:** Final working product definition for v2
**Supersedes:** All previous multi-mode / platform / Mode B planning documents
**Scope:** This document is now the only active product-design and implementation reference for NeuroGPT

---

## 2. Product Decision

NeuroGPT is **not** a multi-mode conversational platform.

NeuroGPT v2 is a **single-purpose digital product** designed to help older adults and their caregivers:

* notice potentially serious neurological symptoms,
* stop minimizing or delaying them,
* understand why they matter,
* and take appropriate next-step action.

This product is **not** a general medical chatbot, not a companionship bot, and not a broad wellness assistant.

Its job is narrow and practical:

> **Move users from symptom uncertainty or minimization toward appropriate help-seeking action.**

---

## 3. Core Product Goal

### Primary Goal

Increase the likelihood that an older adult or caregiver will take neurological symptoms seriously enough to seek timely help.

### Success Definition

The product succeeds when, after interacting with it, the user is more likely to:

* recognise that a symptom may be important,
* understand that waiting may be risky,
* and choose a concrete next step such as calling emergency services, seeking urgent medical care, or arranging prompt clinical follow-up.

### Non-Goals

NeuroGPT v2 does **not** aim to:

* diagnose disease,
* replace a doctor,
* provide definitive triage as a regulated medical device,
* act as a general mental-health or relationships assistant,
* host multiple unrelated product modes,
* provide long-form open-ended companionship.

---

## 4. Product Thesis

Older adults frequently underreact to neurological symptoms because they:

* attribute symptoms to normal ageing,
* hope symptoms will pass,
* do not want to inconvenience family,
* dislike hospitals or fear bad news,
* or do not recognise urgency in time-sensitive conditions.

Traditional health information pages are often too passive. They explain symptoms, but they do not actively move the user toward action.

NeuroGPT v2 fills that gap by combining:

* simple symptom-oriented dialogue,
* clear seriousness framing,
* plain-language explanation,
* and action-oriented prompting.

---

## 5. Target Users

### Primary User

Older adults experiencing possible neurological symptoms or changes.

Examples:

* sudden weakness,
* slurred speech,
* worsening tremor,
* confusion,
* balance changes,
* memory decline,
* seizures or unexplained episodes,
* gait instability,
* sensory changes.

### Secondary User

Caregivers or adult children trying to decide whether an older relative’s symptoms are serious and how urgently they should act.

### Excluded User Framing

The product is not designed primarily for:

* clinicians,
* general health consumers asking broad medical trivia,
* users seeking emotional companionship unrelated to symptom seriousness,
* users seeking a generalized medical encyclopedia.

---

## 6. Product Form

### Chosen Product Form

A **single-page web application** with a structured conversational interface.

### Why this form

This is the most practical and focused MVP because it:

* is fast to build,
* supports guided conversation,
* is easy to test,
* works for both older adults and caregivers,
* and allows controlled output rather than chaotic open chat.

### UI Structure

The interface should have four major areas:

#### A. Symptom Input

A simple input where the user describes what is happening in natural language.

Examples:

* “My mother’s speech became unclear today.”
* “My dad suddenly can’t grip things properly.”
* “She has been getting more confused lately.”

#### B. Guided Follow-Up Questions

The system asks one focused question at a time to clarify:

* onset,
* progression,
* one-sided vs both sides,
* speech change,
* awareness,
* falls,
* associated symptoms,
* duration,
* worsening pattern.

#### C. Seriousness Explanation

The app explains in plain language:

* what features are concerning,
* why they should not be ignored,
* and why delay may matter.

#### D. Next-Step Action Panel

The app presents a concrete recommendation, such as:

* seek emergency help now,
* go to urgent care / emergency department today,
* book prompt medical review,
* monitor specific changes and seek care if worsening occurs.

A caregiver-facing summary should also be generated when helpful.

---

## 7. Core Product Principle

The product should not try to do everything.

It should do one thing well:

> **Turn vague concern into clear action.**

This means the product experience should prioritise:

* clarity over comprehensiveness,
* action over information overload,
* structure over open-ended chatting,
* plain language over medical jargon.

---

## 8. Required Core Functions

NeuroGPT v2 should contain only the functions necessary to support the product goal.

### 8.1 Symptom Intake

The user can describe symptoms in natural language.

### 8.2 Clarification Dialogue

The system can ask structured follow-up questions to reduce ambiguity.

### 8.3 Seriousness Framing

The system can explain why the reported pattern may matter.

This is critical. The product is not only extracting information; it is helping the user **emotionally and cognitively reframe** the symptom as something that may require attention.

### 8.4 Help-Seeking Encouragement

The system can address common forms of hesitation, such as:

* “It’s probably just old age.”
* “I don’t want to make a fuss.”
* “We can wait until tomorrow.”
* “It might go away.”

### 8.5 Action Recommendation

The system provides a clear next step in simple language.

### 8.6 Caregiver Summary

Where useful, the system outputs a concise summary the user can show or send to a family member.

---

## 9. What We Are Intentionally Removing

The following concepts are removed from scope:

* multi-mode architecture,
* Mode B,
* unrelated emotional / identity / relationships modules,
* platform framing,
* broad agent-routing logic,
* speculative future assistants unrelated to the core product.

NeuroGPT v2 must have **one product identity, one user problem, and one implementation path**.

---

## 10. Do We Need “Escalation” and “Triage” as Big System Concepts?

### Product Decision

We should **not** make “escalation” and “triage” the centre of the product narrative or document structure.

### Why

Those terms are too system-centric and make the project sound like:

* a hospital workflow engine,
* a regulated decision-support platform,
* or a complex medical triage system.

That is **not** the product you are building.

### What to do instead

Keep the user-facing and product-facing framing much simpler:

* **Is this symptom pattern potentially serious?**
* **Should the user act now, soon, or monitor and arrange follow-up?**
* **How do we help the user take it seriously?**

### Important nuance

Internally, the application may still use:

* symptom risk logic,
* urgency categories,
* and decision rules.

But these should remain **implementation details**, not the identity of the product.

So the answer is:

* **Do not build the whole product around “escalation triage” language.**
* **Do keep lightweight internal urgency logic in the backend.**

---

## 11. Product Logic

### High-Level Logic Flow

1. User describes a symptom or change.
2. System identifies missing details.
3. System asks structured follow-up questions.
4. System determines how concerning the reported pattern may be.
5. System explains why the symptom should or should not be taken seriously.
6. System addresses hesitation or minimisation.
7. System gives a next-step recommendation.
8. System generates a caregiver-facing summary if needed.

This is the whole product loop.

---

## 12. Knowledge Strategy

### Phase 1 Decision

Do **not** begin with a large or complex RAG system.

The first MVP should work with:

* a small, curated, high-trust knowledge base,
* and controlled internal logic.

### Why

At this stage, the bottleneck is not “lack of medical knowledge.”
The bottleneck is whether the product can:

* interpret symptom descriptions,
* frame seriousness clearly,
* and motivate action safely.

### Initial Knowledge Scope

The curated knowledge base should focus only on content needed for the product goal:

* warning signs of common neurological emergencies,
* common symptom patterns in older adults,
* plain-language explanations of why timely care matters,
* caregiver communication guidance.

### Retrieval Role

Knowledge retrieval should support:

* explanation,
* clarity,
* and educational reinforcement.

It should not become the main decision-maker.

---

## 13. MVP Definition

### MVP Version Must Include

* natural-language symptom input,
* guided follow-up questions,
* seriousness explanation,
* hesitation-handling response generation,
* clear action recommendation,
* caregiver summary output.

### MVP Version Must Not Include

* multiple product modes,
* generalized memory-heavy conversation,
* unrelated wellness modules,
* broad open-domain medical QA,
* large-scale complex retrieval architecture,
* clinician dashboards,
* account systems unless needed later.

---

## 14. Experience Design Requirements

The product must be understandable to non-experts.

### Interaction Style

* one question at a time,
* large readable text,
* low cognitive load,
* minimal jargon,
* clear visual hierarchy,
* short explanations followed by action.

### Tone

The tone should be:

* calm,
* respectful,
* clear,
* non-alarmist,
* but firm when the symptom pattern may be dangerous.

### UX Requirement

The interface should reduce decision paralysis.
The user should never finish a session wondering:

* “So what am I supposed to do now?”

---

## 15. Core Behavioral Requirement

The single hardest product requirement is this:

> The system must be able to respond well when the user is minimising or delaying action.

This is not a side feature. It is central to the product.

The system must handle statements such as:

* “It’s probably nothing.”
* “She always gets like this.”
* “We’ll just wait.”
* “He doesn’t want to see a doctor.”
* “I don’t want to overreact.”

The response should:

* acknowledge the user’s reluctance,
* explain why waiting may be risky,
* and redirect them toward a concrete next step.

---

## 16. System Scope for Implementation

To keep engineering practical, the system should be built as a small set of modules:

### Suggested Internal Modules

* `symptom_extractor`
* `question_manager`
* `concern_estimator`
* `response_builder`
* `knowledge_retriever`
* `summary_generator`

These module names are implementation details only. They should not imply a multi-mode platform.

---

## 17. Data Strategy

### Immediate Data Need

The project should begin with a small manually created dataset containing:

* common neurological symptom descriptions,
* common older-adult or caregiver wording,
* common forms of minimisation,
* mapped seriousness explanations,
* and mapped next-step action recommendations.

### Priority Data Types

The most valuable early data is not broad disease text. It is:

1. how users actually describe symptoms,
2. how users justify delay,
3. and what explanation wording successfully pushes action.

---

## 18. Evaluation Criteria

The product should be judged on whether it improves action-readiness.

### Key Evaluation Questions

* Does the user better understand that the symptom may matter?
* Does the user better understand why delay could be harmful?
* Does the user leave with a concrete next step?
* In concerning scenarios, does the system communicate urgency clearly without being chaotic?
* For hesitant users, does the system increase willingness to seek help?

---

## 19. Repository and Documentation Decision

This PRD / RFC is now the **only active product-definition document**.

All old documents related to:

* platform-wide mode architecture,
* Mode B,
* unrelated future modes,
* or conflicting product narratives,

should be archived and removed from the active build path.

No new active design document should be created unless it directly supports this single-product definition.

---

## 20. Final Product Statement

NeuroGPT v2 is a focused digital tool for older adults and caregivers.

It does not aim to be a broad medical platform.
It does not aim to host multiple assistants.
It does not aim to simulate a full clinical workflow.

It exists to do one practical thing well:

> **help users recognise potentially serious neurological symptoms and move them toward timely help-seeking action.**

That is the product.
