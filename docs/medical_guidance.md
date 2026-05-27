# Minimal Medical Guidance Cards

NeuroGPT uses a small deterministic guidance-card layer to add short, conservative source-backed explanations to responses. This is not full RAG: there are no embeddings, vector databases, semantic retrieval, external web search, LangChain, or additional LLM calls.

Guidance cards only explain an action tier that has already been selected by the deterministic pipeline. They do not diagnose, choose care settings, decide `action_level`, change `concern_level`, or override `risk_rules`/`action_mapper`.

## Implemented Cards

- `stroke_red_flags`: CDC Signs and Symptoms of Stroke (`https://www.cdc.gov/stroke/signs-symptoms/index.html`) and American Stroke Association Stroke Symptoms (`https://www.stroke.org/en/about-stroke/stroke-symptoms`). Used for already-escalated stroke-like neurological warning signs such as sudden one-sided weakness/numbness, facial droop, speech trouble, vision change, or gait/balance trouble.
- `sudden_confusion`: NHS sudden confusion/delirium (`https://www.nhs.uk/symptoms/confusion/`) and NICE Delirium CG103 (`https://www.nice.org.uk/guidance/cg103/chapter/Recommendations`). Used for sudden confusion or acute awareness/cognitive changes that already map to urgent/emergency action.
- `severe_headache`: Mayo Clinic headache urgent-care guidance (`https://www.mayoclinic.org/symptoms/headache/basics/when-to-see-doctor/sym-20050800`). Used for severe or sudden headache red flags that already map to urgent/emergency action.
- `fall_head_injury`: NICE Head injury NG232 (`https://www.nice.org.uk/guidance/ng232/chapter/Recommendations`). Used for fall/head-injury red flags such as loss of consciousness, seizure, vomiting/headache context, or focal neurological concerns.
- `suicidal_language`: NIMH Warning Signs of Suicide (`https://www.nimh.nih.gov/health/publications/warning-signs-of-suicide`) and NIMH Suicide Prevention (`https://www.nimh.nih.gov/health/topics/suicide-prevention`). Uses a narrow phrase detector for direct self-harm/suicide language and generic local crisis/emergency-service wording.

## Source Handling

Source names and URLs are stored as metadata in `configs/medical_guidance.yaml`. Normal elder-facing responses show only short snippets, not raw URLs. Generated live-eval reports remain separate from product scenario and guidance test commits.

## Safety Boundaries

Cards use phrases such as "stroke-like warning signs" and "serious causes need to be ruled out." They intentionally avoid diagnostic claims such as "you have stroke," "确诊," or "一定是."

## Response Tone

Elder-facing wording should use short sentences, calm action language, and low cognitive load. It should separate what was noticed, why action is recommended, and what to do next. Emergency responses stay direct, but should avoid repeated panic wording.

Caregiver summaries should be short handoffs: observed signs, timing if known, escalation rationale if present, and the recommended next action. They should not expose internal tier labels or technical extraction status.

If LLM extraction degrades or fails, normal responses should remain usable and calm. Do not mention provider names, timeouts, API failures, JSON parsing, DeepSeek, or fallback mode to elder users or caregivers.

Monitor or ambiguous cases should avoid false reassurance. They should say that no clear emergency pattern is currently identified, then explain what changes should trigger reassessment or escalation.

Future expansion can move this reviewed card set into a broader medical knowledge system, but that should happen only after the deterministic card behavior remains stable and reviewed.
