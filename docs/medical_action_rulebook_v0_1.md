# NeuroGPT Medical Action Rulebook v0.1

Date: 2026-05-14

Purpose: define the first source-backed action-tier logic for NeuroGPT. This is not a diagnosis engine. It is a help-seeking action engine for older adults and caregivers.

Clinical boundary: NeuroGPT should identify when a user should seek emergency help, same-day care, prompt clinical review, or answer one critical follow-up question. It must not tell users that they have or do not have a specific diagnosis.

Source policy: use public, reliable sources only. If a rule is not clearly supported by the cited source, mark `evidence_status: needs_source` and `requires_medical_review: true`.

## Action Tiers

Use these rulebook tiers when drafting `configs/risk_rules.yaml`. Current code does not yet expose all of them as `ActionLevel` enum values; see the mismatch report.

| Rulebook tier | Meaning | Current closest implementation |
| --- | --- | --- |
| `emergency_now` | Call local emergency services now or go to emergency care. Use for source-backed emergency red flags. | `ActionLevel.EMERGENCY_NOW` |
| `ask_critical_followup` | Ask one short, safety-critical question before final action. This is not a final medical action. | `needs_follow_up_question=True` |
| `same_day_review` | Seek same-day urgent clinical assessment when emergency criteria are not met but the condition should not wait. | `ActionLevel.SAME_DAY_REVIEW` |
| `prompt_clinical_review` | Arrange prompt non-emergency medical review, commonly primary care, neurology, falls service, memory clinic, or eye care depending on symptom. | closest current enum is `PROMPT_FOLLOW_UP`; not present as named tier |
| `monitor_with_safety_net` | Monitor only when symptoms are chronic, stable, mild, and no red flags are present; include clear escalation triggers. | `ActionLevel.MONITOR` |

## Global Required Fields

These fields are cross-cutting and should be asked or extracted whenever safe:

- Last known well / exact onset time.
- Sudden vs gradual vs chronic course.
- Current vs resolved symptoms and duration.
- First episode vs recurrent known condition.
- Laterality: one side, both sides, face/arm/leg, eye.
- Associated stroke signs: face droop, arm/leg weakness or numbness, speech/language trouble, vision change, balance/gait change, sudden severe headache.
- Head injury, fall, seizure, loss of consciousness, or altered awareness.
- Baseline function, known dementia/Parkinson's/epilepsy/stroke history, anticoagulant use if known.

## Known Mismatch Report

### M1: Speech/language symptoms can bypass onset clarification

Status: known mismatch, do not fix in code yet.

Files involved:

- `modules/question_manager.py`
- `configs/risk_rules.yaml`
- `modules/symptom_extractor.py`
- `core/risk_stratifier.py`
- `tests/*`

Current behavior:

- `modules/question_manager.py` treats `rf.slurred_speech` and `rf.stroke_beFAST` as high-risk red flags in `_has_high_risk_red_flags()`, so `decide_question()` returns `None` before asking onset/duration.
- `configs/risk_rules.yaml` treats high-risk speech/language disturbance as dependent on `onset: sudden` for `STROKE_BEFAST`, `SUDDEN_FACIAL_DROOP`, and `SUDDEN_SPEECH`.
- `modules/symptom_extractor.py` sets `slurred_speech=True` from broad phrases such as Chinese "讲话不清/说话不清/口齿不清/含糊" and English "slurred/speech", even when onset is unknown.
- `modules/symptom_extractor.py` also sets `stroke_beFAST = weakness_one_side or facial_droop or slurred_speech`; this makes isolated speech wording look like a FAST red flag even without confirmed sudden onset.
- `core/risk_stratifier.py` would not match `SUDDEN_SPEECH` unless `symptoms.onset == "sudden"`, but the pipeline asks questions before calling the risk stratifier.
- Tests cover sudden stroke-like scenarios, but there is no regression test for "speech symptom with unknown onset should ask onset/duration first" or "I don't know how to express the symptom" should not trigger neurological speech handling.

Rulebook target behavior for speech/language:

- Sudden speech/language difficulty -> `emergency_now`.
- Speech/language difficulty with unknown onset and no other immediately emergency features -> `ask_critical_followup` for onset/duration/last-known-well.
- Chronic or gradual speech/language difficulty without acute red flags -> `prompt_clinical_review`, not `emergency_now`.
- User says "我不知道怎么表达这个症状" / "I don't know how to express the symptom" -> not a neurological speech symptom; ask an open symptom-clarification question.

Evidence note:

- Sudden speech/language trouble as a stroke warning sign is source-backed by CDC, AHA/ASA, NHS, and NINDS.
- The "unknown onset -> ask one follow-up rather than immediate emergency escalation" workflow is source-informed because public stroke sources emphasize sudden onset and recording onset time, but it is not explicitly endorsed as a downgrade rule. Mark implementation as `evidence_status: needs_source_for_non_emergency_downgrade` and `requires_medical_review: true`.

### M2: Rule engine supports YAML conditions that current symptom model cannot produce

Examples:

- `configs/risk_rules.yaml` references `no_clear_speech`, `inability_to_speak`, `confusion_language`, `arm_weakness_one_side`, `postictal_confusion`, `focal_movement`, `eye_pain`, `scalp_tenderness`, `jaw_claudication`, `speech_disturbance`, `seizure_after`, `near_falls`, `fear_of_falling`, `injury_from_fall`, `difficulty_with_tasks`, `leg_weakness`, `back_pain`, `daytime_functional_impact`, `dream_enactment`, `shouting_in_sleep`, and `violent_movements_during_sleep`.
- `core/types.py` / `RedFlags` and `ExtractedSymptoms` do not define many of these fields.
- `core/risk_stratifier.py` silently treats missing flags as false through `symptom_flags.get(...)`.

Impact:

- Some YAML rules look clinically broader than they are in runtime.
- Some OR branches can never match.

Implementation note:

- Before expanding source-backed rules, align extractable fields, YAML condition names, and test fixtures.

### M3: `STROKE_BEFAST` description and runtime conditions do not fully match

Current YAML description: "Sudden onset + one-sided weakness + speech difficulty".

Current runtime conditions:

- `onset: sudden`
- `laterality: one_side`
- OR speech flags

The rule does not explicitly require `weakness_one_side: true`; it only requires `laterality == one_side`. That can overstate the condition if laterality came from a phrase unrelated to weakness.

Implementation note:

- Split BE-FAST components into separate explicit source-backed rules: face, arm/leg weakness or numbness, speech/language, vision, balance, severe headache.

### M4: Current action vocabulary lacks `prompt_clinical_review`

The rulebook uses `prompt_clinical_review` for chronic/gradual neurological symptoms without acute red flags. `core/types.py` has `PROMPT_FOLLOW_UP`, `SAME_DAY_REVIEW`, and `MONITOR`, but no named clinical-review tier.

Implementation note:

- Either add `ActionLevel.PROMPT_CLINICAL_REVIEW` or define a clear mapping from rulebook `prompt_clinical_review` to existing product actions.

### M5: Some YAML anchor symptoms are not enforced by current OR semantics

Current `core/risk_stratifier.py` treats `requires_all: false` as "any check can match." Several rules are written as if the anchor symptom must be present and the OR group is an associated-feature group.

Examples:

- `HEAD_INJURY_NEURO` can match `confusion`, `loss_of_consciousness`, `weakness`, `vision_loss`, `seizure`, or `severe_headache` even if `head_injury` is false.
- `SEIZURE` can match `loss_of_consciousness` or other secondary features even if `seizure` is false.
- `SUDDEN_SEVERE_HEADACHE` can match sudden focal/vision/confusion features even if `severe_headache` is false.
- `SUDDEN_FACIAL_DROOP` can match sudden one-sided slurred speech or arm weakness even if `facial_droop` is false.

Impact:

- Runtime action tiers may be assigned for the wrong reason code.
- Source-backed rulebook logic should require anchor symptoms explicitly, then evaluate associated red flags.

Implementation note:

- For v0.1 YAML, use explicit structures such as `requires: [head_injury]` plus `any_of: [...]`, or keep `requires_all: true` and make OR groups one named condition.

### M6: Tests do not yet protect follow-up gating

Current tests cover high-risk stroke scenarios with sudden onset and combined weakness/speech signs. Missing tests:

- Isolated slurred speech with `onset=UNKNOWN` should ask onset/duration.
- Isolated word-finding difficulty with `onset=UNKNOWN` should ask onset/duration.
- User phrase "I don't know how to describe the symptom" should not set `slurred_speech`, `word_finding_difficulty`, or `stroke_beFAST`.
- Chronic stable speech problem without acute red flags should not map to `emergency_now`.
- `question_manager.py` should not suppress follow-up solely because `slurred_speech=True`.

## Symptom Families

### 1. Speech/language Difficulty

`requires_medical_review: true`

Symptom family name: speech/language difficulty.

Key user phrases:

- Chinese: "说话不清", "讲话含糊", "口齿不清", "说不出话", "突然不会说话", "听不懂别人说话", "别人听不懂他说什么", "找词困难", "叫不出名字", "失语".
- English: "slurred speech", "speech is unclear", "can't speak", "trouble speaking", "trouble understanding speech", "word-finding difficulty", "aphasia", "can't get words out".
- Not a neurological speech symptom by itself: "我不知道怎么表达这个症状", "我不知道怎么描述", "I don't know how to express/describe the symptom".

Red-flag features:

- Sudden speech or language trouble.
- Speech/language trouble with face droop, one-sided arm/leg weakness or numbness, vision change, balance/gait difficulty, sudden severe headache, acute confusion, seizure, loss of consciousness, or head injury.
- Current or recently resolved speech symptoms that sound stroke-like or TIA-like.

Missing critical fields to ask:

- "When was the person last normal / last known well?"
- "Did the speech/language problem start suddenly or gradually?"
- "Is it still happening? If not, how long did it last?"
- "Is this slurred speech, trouble finding words, inability to speak, or trouble understanding?"
- "Any face droop, one-sided weakness/numbness, vision loss, balance trouble, severe headache, confusion, seizure, or head injury?"

Action-tier mapping:

| Condition | Action tier | evidence_status | Reason codes |
| --- | --- | --- | --- |
| Sudden speech/language difficulty | `emergency_now` | `source_backed` | `STROKE_SPEECH_SUDDEN`, `FAST_SPEECH` |
| Speech/language difficulty plus any other stroke warning sign | `emergency_now` | `source_backed` | `STROKE_MULTI_SIGN`, `FAST_SPEECH_WITH_FOCAL_DEFICIT` |
| Speech/language difficulty after head injury, seizure, or altered consciousness | `emergency_now` | `source_backed` | `HEAD_INJURY_NEURO_SPEECH`, `SEIZURE_OR_LOC_WITH_SPEECH` |
| Speech/language difficulty with unknown onset and no other emergency features | `ask_critical_followup` | `needs_source_for_non_emergency_downgrade` | `SPEECH_ONSET_UNKNOWN_ASK` |
| Gradual/chronic speech or word-finding difficulty without acute red flags | `prompt_clinical_review` | `source_backed` | `SPEECH_GRADUAL_REVIEW`, `LANGUAGE_COGNITIVE_REVIEW` |
| "I don't know how to express the symptom" | `ask_critical_followup` for open clarification | `product_semantics_not_clinical_claim` | `NOT_NEURO_SPEECH_CLARIFY` |

Unsafe wording to avoid:

- "It is probably just aging."
- "It is only speech, so it can wait."
- "This is definitely a stroke."
- "If there is no weakness, it is not urgent."
- "Sleep on it and see tomorrow" for sudden speech/language symptoms.

Implementation notes for `risk_rules.yaml`:

- Do not let `slurred_speech: true` alone suppress follow-up when `onset == unknown`.
- Create distinct flags for observed symptom vs emergency red flag, for example `speech_language_symptom_present` and `sudden_speech_language_deficit`.
- `stroke_beFAST` should not be set by isolated speech wording unless onset or FAST context is known, or it should be treated as "possible FAST component" rather than final emergency gate.
- Add a rule for `onset: unknown` + speech/language symptom -> ask onset/duration.
- Add a negative/clarification path for "I don't know how to describe the symptom".

Source citations:

- CDC stroke signs and symptoms: https://www.cdc.gov/stroke/signs-symptoms/index.html
- American Stroke Association F.A.S.T. warning signs: https://www.stroke.org/en/about-stroke/stroke-symptoms
- NHS stroke symptoms: https://www.nhs.uk/conditions/stroke/symptoms/
- NINDS stroke page: https://www.ninds.nih.gov/health-information/disorders/stroke

### 2. One-sided Weakness/numbness/facial Droop

`requires_medical_review: true`

Symptom family name: one-sided weakness, numbness, or facial droop.

Key user phrases:

- Chinese: "一侧无力", "半边身子没力气", "左/右手抬不起来", "一边脸歪", "嘴歪", "面瘫", "一侧麻木", "半身发麻".
- English: "one-sided weakness", "arm weakness", "face drooping", "facial droop", "one side is numb", "can't lift one arm", "left/right side won't move".

Red-flag features:

- Sudden weakness or numbness of face, arm, or leg, especially on one side.
- Facial droop or arm drift.
- Any associated speech/language trouble, vision change, balance difficulty, severe headache, confusion, seizure, loss of consciousness.
- Symptoms that resolved but occurred suddenly, consistent with possible TIA warning.

Missing critical fields to ask:

- Last known well / exact onset time.
- Sudden vs gradual, current vs resolved, duration.
- Body part: face, arm, leg, hand; one side or both.
- Associated speech, vision, balance, headache, confusion, seizure, head injury.
- Prior stroke/TIA or baseline weakness.

Action-tier mapping:

| Condition | Action tier | evidence_status | Reason codes |
| --- | --- | --- | --- |
| Sudden one-sided weakness or numbness | `emergency_now` | `source_backed` | `STROKE_UNILATERAL_WEAKNESS_SUDDEN`, `STROKE_UNILATERAL_NUMBNESS_SUDDEN` |
| Sudden facial droop | `emergency_now` | `source_backed` | `FAST_FACE_DROOP` |
| One-sided weakness/numbness/facial droop plus speech, vision, balance, severe headache, confusion, seizure, or loss of consciousness | `emergency_now` | `source_backed` | `STROKE_FOCAL_WITH_ASSOCIATED_RED_FLAG` |
| New current one-sided deficit with unknown onset | `emergency_now` unless clearly chronic/stable | `source_inferred_needs_medical_review` | `FOCAL_DEFICIT_ONSET_UNKNOWN_CURRENT` |
| Chronic stable one-sided symptoms without acute change | `prompt_clinical_review` | `source_backed_for_review_not_emergency` | `FOCAL_DEFICIT_CHRONIC_REVIEW` |

Unsafe wording to avoid:

- "It is probably arthritis or age."
- "Wait to see if one-sided weakness improves."
- "Facial droop is harmless if speech is normal."
- "This is definitely Bell's palsy/stroke."

Implementation notes for `risk_rules.yaml`:

- Separate `weakness_one_side`, `focal_numbness_one_side`, and `facial_droop`.
- Do not rely only on `laterality: one_side`; require the focal deficit flag that made laterality relevant.
- Add explicit TIA-like "resolved sudden focal deficit" handling if duration/resolution can be extracted.

Source citations:

- CDC stroke signs and symptoms: https://www.cdc.gov/stroke/signs-symptoms/index.html
- American Stroke Association F.A.S.T. warning signs: https://www.stroke.org/en/about-stroke/stroke-symptoms
- NHS stroke symptoms: https://www.nhs.uk/conditions/stroke/symptoms/
- NINDS stroke page: https://www.ninds.nih.gov/health-information/disorders/stroke

### 3. Acute Confusion / Altered Awareness

`requires_medical_review: true`

Symptom family name: acute confusion / altered awareness.

Key user phrases:

- Chinese: "突然糊涂", "突然不认人", "意识不清", "神志不清", "叫不醒", "反应很慢", "胡言乱语", "和平时不一样", "突然很嗜睡".
- English: "suddenly confused", "not making sense", "does not recognize family", "altered mental status", "hard to wake", "very drowsy", "not acting like themselves", "delirious".

Red-flag features:

- Sudden confusion or rapidly changed awareness.
- Drowsy, hard to wake, or unresponsive.
- Confusion with stroke signs, seizure, severe headache, fever/neck stiffness, head injury, breathing difficulty, or suspected poisoning/medication issue.
- Recent fluctuating change in cognition, perception, physical function, or social behavior in an older adult.

Missing critical fields to ask:

- Onset: minutes/hours/days vs gradual months.
- Current alertness: awake, hard to wake, unresponsive.
- Baseline dementia or memory problems.
- Fever, infection symptoms, dehydration, new medications, alcohol/substance exposure, diabetes/low blood sugar risk.
- Any focal neurological signs, seizure, fall/head injury, severe headache, breathing difficulty.

Action-tier mapping:

| Condition | Action tier | evidence_status | Reason codes |
| --- | --- | --- | --- |
| Sudden confusion or altered awareness | `emergency_now` | `source_backed` | `ACUTE_CONFUSION_EMERGENCY`, `DELIRIUM_SUDDEN_CHANGE` |
| Confusion plus drowsy/unresponsive, seizure, stroke signs, head injury, severe headache, fever/neck stiffness, or breathing difficulty | `emergency_now` | `source_backed` | `ALTERED_AWARENESS_WITH_RED_FLAG` |
| Recent hours/days fluctuating confusion in older adult, not clearly emergency in wording | `same_day_review` or `emergency_now` if worsening/unsafe | `source_backed_needs_medical_review` | `POSSIBLE_DELIRIUM_SAME_DAY` |
| Gradual cognitive/behavior change over weeks/months without acute altered awareness | `prompt_clinical_review` | `source_backed` | `COGNITIVE_GRADUAL_REVIEW` |

Unsafe wording to avoid:

- "Confusion is normal in old age."
- "This is probably dementia, so no urgent action is needed."
- "Let them sleep it off" when awareness is altered.
- "It is just a UTI" without medical assessment.

Implementation notes for `risk_rules.yaml`:

- `acute_confusion` should require sudden/recent onset or altered awareness to trigger `emergency_now`.
- Add fields for `hard_to_wake`, `unresponsive`, `fluctuating_awareness`, and `baseline_dementia`.
- Distinguish acute delirium-like confusion from gradual memory decline.

Source citations:

- NHS sudden confusion: https://www.nhs.uk/conditions/confusion/
- NICE delirium guideline CG103: https://www.nice.org.uk/guidance/cg103/chapter/Recommendations
- CDC stroke signs and symptoms: https://www.cdc.gov/stroke/signs-symptoms/index.html

### 4. Seizure / Loss of Consciousness

`requires_medical_review: true`

Symptom family name: seizure / loss of consciousness.

Key user phrases:

- Chinese: "抽搐", "癫痫发作", "全身抖动", "翻白眼", "口吐白沫", "晕倒", "昏倒", "失去意识", "叫不醒", "黑了一下".
- English: "seizure", "fit", "convulsion", "shaking episode", "passed out", "fainted", "blackout", "lost consciousness", "unconscious".

Red-flag features:

- Seizure lasting more than 5 minutes.
- Repeated seizures or another seizure soon after.
- First-ever seizure.
- Trouble breathing or trouble waking/recovering.
- Seizure with injury, head injury, water exposure, pregnancy, diabetes, or known serious condition.
- Loss of consciousness with persistent confusion, weakness, speech change, severe headache, chest pain, or head injury.

Missing critical fields to ask:

- Duration of seizure/LOC.
- First episode or known epilepsy/syncope history.
- Returned fully to baseline? How long after?
- Breathing normally?
- Injury, fall, head strike, water exposure.
- Repeated events.
- Diabetes, pregnancy, anticoagulants, new medications, alcohol/substances if known.
- Focal weakness/speech/vision changes after the event.

Action-tier mapping:

| Condition | Action tier | evidence_status | Reason codes |
| --- | --- | --- | --- |
| Active seizure >5 minutes or repeated seizures | `emergency_now` | `source_backed` | `SEIZURE_OVER_5_MIN`, `SEIZURE_REPEATED` |
| First-ever seizure | `emergency_now` | `source_backed` | `SEIZURE_FIRST_TIME` |
| Seizure with breathing trouble, failure to wake/recover, serious injury, head injury, water exposure, pregnancy, diabetes, or focal neurological symptom | `emergency_now` | `source_backed` | `SEIZURE_COMPLICATED` |
| Loss of consciousness with injury, persistent altered awareness, focal neurological signs, severe headache, or head injury | `emergency_now` | `source_backed` | `LOC_WITH_RED_FLAG` |
| Known brief seizure, fully recovered, no injury, no red flags | `prompt_clinical_review` / follow existing care plan | `source_backed_needs_medical_review` | `KNOWN_SEIZURE_RECOVERED_REVIEW` |
| Unexplained faint/blackout with full recovery and no red flags | `same_day_review` | `source_backed_needs_medical_review` | `TLOC_UNEXPLAINED_REVIEW` |

Unsafe wording to avoid:

- "All seizures are harmless if they stop."
- "Wait out a seizure longer than 5 minutes."
- "They woke up, so no follow-up is needed."
- "It was only fainting" without assessing injury and neurological symptoms.

Implementation notes for `risk_rules.yaml`:

- Add explicit fields: `seizure_duration_over_5_min`, `repeated_seizures`, `first_seizure`, `not_recovered`, `breathing_difficulty`, `seizure_in_water`.
- Current YAML references `postictal_confusion` and `focal_movement`; add model support or remove unreachable fields.
- Treat LOC as a family needing its own follow-up fields; current `LOSS_OF_CONSCIOUSNESS` OR fields include some unreachable names.

Source citations:

- CDC seizure first aid: https://www.cdc.gov/epilepsy/first-aid-for-seizures/index.html
- NHS seizure first aid: https://www.nhs.uk/conditions/what-to-do-if-someone-has-a-seizure-fit/
- NICE transient loss of consciousness guideline CG109: https://www.nice.org.uk/guidance/cg109/chapter/Recommendations

### 5. Gait/balance/falls/head Injury

`requires_medical_review: true`

Symptom family name: gait, balance, falls, or head injury.

Key user phrases:

- Chinese: "走路不稳", "平衡差", "容易摔倒", "最近跌倒", "反复摔倒", "摔到头", "撞到头", "头部受伤", "脚拖地", "步态变了".
- English: "unsteady walking", "loss of balance", "fall", "recurrent falls", "hit head", "head injury", "trouble walking", "shuffling gait", "dragging foot".

Red-flag features:

- Sudden trouble walking, dizziness, loss of balance, or coordination as a stroke warning sign.
- Fall/head injury with loss of consciousness, worsening headache, repeated vomiting, seizure, slurred speech, weakness/numbness, confusion, unusual behavior, unequal pupils, drowsiness or inability to wake.
- Fall with anticoagulant use, suspected fracture, severe pain, inability to stand/walk, or recurrent unexplained falls.
- Progressive gait instability or recurrent falls in an older adult.

Missing critical fields to ask:

- Did they hit their head? Any loss of consciousness?
- Vomiting, worsening headache, confusion, seizure, speech/vision/weakness/numbness after the fall?
- Can they stand/walk now? Any severe pain or suspected fracture?
- Number of falls and timeframe.
- Sudden vs gradual balance/gait change.
- Medications, anticoagulants, dizziness, fainting, baseline mobility aids if known.

Action-tier mapping:

| Condition | Action tier | evidence_status | Reason codes |
| --- | --- | --- | --- |
| Sudden gait/balance/coordination trouble with stroke-like context | `emergency_now` | `source_backed` | `STROKE_BALANCE_SUDDEN` |
| Head injury with neurological danger sign, seizure, LOC, worsening headache, repeated vomiting, slurred speech, weakness/numbness, confusion, or drowsiness | `emergency_now` | `source_backed` | `HEAD_INJURY_DANGER_SIGN` |
| Fall with inability to get up/walk, severe injury, suspected fracture, or high-risk medication context | `same_day_review` or `emergency_now` depending severity | `source_backed_needs_medical_review` | `FALL_INJURY_URGENT` |
| Recurrent falls or gait/balance abnormality in older adult without acute injury | `prompt_clinical_review` | `source_backed` | `RECURRENT_FALLS_REVIEW`, `GAIT_BALANCE_REVIEW` |
| Chronic stable mild balance concern, no falls, no red flags | `prompt_clinical_review` or `monitor_with_safety_net` | `needs_source` | `GAIT_STABLE_MONITOR_NEEDS_SOURCE` |

Unsafe wording to avoid:

- "Falls are normal when people get older."
- "No need to check after a head injury if they seem okay."
- "Just rest at home" after head injury with neurological symptoms.
- "Balance problems are not neurological."

Implementation notes for `risk_rules.yaml`:

- Current `HEAD_INJURY_NEURO` is directionally aligned but should include CDC/NHS danger-sign fields.
- Add extractable fields for vomiting, worsening headache, drowsy/unable to wake, unequal pupils, anticoagulant use, unable_to_walk, severe_injury.
- Align recurrent falls with NICE falls assessment rather than emergency language unless acute injury/red flags are present.

Source citations:

- CDC TBI danger signs: https://www.cdc.gov/traumatic-brain-injury/signs-symptoms/index.html
- NHS head injury advice: https://www.nhs.uk/conditions/head-injury-and-concussion/
- NICE falls guideline NG249: https://www.nice.org.uk/guidance/ng249/chapter/Recommendations
- CDC older adult fall prevention: https://www.cdc.gov/falls/older-adult-falls/index.html
- CDC stroke signs and symptoms: https://www.cdc.gov/stroke/signs-symptoms/index.html

### 6. Vision Change

`requires_medical_review: true`

Symptom family name: vision change.

Key user phrases:

- Chinese: "突然看不见", "视力突然下降", "一只眼看不清", "复视", "重影", "视野缺损", "眼前发黑", "看东西模糊".
- English: "sudden vision loss", "blurred vision", "double vision", "can't see from one eye", "visual field loss", "curtain over vision", "loss of sight".

Red-flag features:

- Sudden trouble seeing in one or both eyes, especially with other stroke signs.
- Sudden vision loss, new double vision, or visual field loss.
- Vision change with severe headache, eye pain, jaw pain/scalp tenderness, neurological symptoms, head injury, or acute confusion.

Missing critical fields to ask:

- Sudden vs gradual, exact onset.
- One eye or both eyes; complete loss, partial field loss, blurry, double vision.
- Current vs resolved and duration.
- Eye pain, headache, jaw pain, scalp tenderness, trauma.
- Associated speech/weakness/numbness/balance/confusion.

Action-tier mapping:

| Condition | Action tier | evidence_status | Reason codes |
| --- | --- | --- | --- |
| Sudden vision loss or sudden trouble seeing with stroke signs | `emergency_now` | `source_backed` | `STROKE_VISION_SUDDEN` |
| Sudden vision loss without other neurological symptoms | `emergency_now` or same-day emergency eye care depending local pathway | `source_backed_needs_medical_review` | `VISION_LOSS_SUDDEN` |
| New double vision with neurological symptoms | `emergency_now` | `source_backed` | `DIPLOPIA_WITH_NEURO_RED_FLAG` |
| Gradual vision decline without neuro red flags | `prompt_clinical_review` / eye care | `source_backed` | `VISION_GRADUAL_REVIEW` |

Unsafe wording to avoid:

- "It is just aging eyes."
- "Sudden vision loss can wait for a routine appointment."
- "If only one eye is affected, it is not urgent."
- "This is definitely a stroke."

Implementation notes for `risk_rules.yaml`:

- Split `vision_loss` into `sudden_vision_loss`, `monocular_vision_loss`, `binocular_vision_loss`, `double_vision`, and `visual_field_loss` if extractor support is added.
- Current `SUDDEN_VISION_LOSS` requires OR features like eye pain/headache/scalp tenderness/jaw claudication; rulebook should allow sudden vision loss itself to prompt urgent/emergency action.

Source citations:

- CDC stroke signs and symptoms: https://www.cdc.gov/stroke/signs-symptoms/index.html
- NHS stroke symptoms: https://www.nhs.uk/conditions/stroke/symptoms/
- NHS sudden vision loss: https://www.nhs.uk/conditions/vision-loss/
- National Eye Institute eye emergencies: https://www.nei.nih.gov/learn-about-eye-health/healthy-vision/eye-health-emergencies

### 7. Severe Headache

`requires_medical_review: true`

Symptom family name: severe headache.

Key user phrases:

- Chinese: "突然剧烈头痛", "爆炸样头痛", "一生最严重的头痛", "雷击样头痛", "头痛伴呕吐", "头痛伴脖子僵硬".
- English: "sudden severe headache", "worst headache of life", "thunderclap headache", "explosive headache", "severe headache with vomiting", "headache with stiff neck".

Red-flag features:

- Sudden severe headache with no known cause.
- Severe headache with weakness/numbness, speech trouble, confusion, vision loss/double vision, seizure, loss of consciousness, fever or neck stiffness.
- Severe headache after head injury.
- New severe headache in older adult or headache with jaw pain/scalp tenderness/visual symptoms needs urgent clinical review.

Missing critical fields to ask:

- Exact onset: sudden peak vs gradual.
- Worst ever/new type? Current severity.
- Associated neurological signs, confusion, seizure, vision changes, fainting.
- Fever/neck stiffness/rash, vomiting.
- Head injury.
- Age, anticoagulants, cancer/immunosuppression if known.

Action-tier mapping:

| Condition | Action tier | evidence_status | Reason codes |
| --- | --- | --- | --- |
| Sudden severe / thunderclap headache | `emergency_now` | `source_backed` | `HEADACHE_THUNDERCLAP` |
| Severe headache with neurological sign, seizure, altered awareness, vision loss, or head injury | `emergency_now` | `source_backed` | `HEADACHE_WITH_NEURO_RED_FLAG` |
| Severe headache with fever/neck stiffness | `emergency_now` | `source_backed` | `HEADACHE_MENINGEAL_RED_FLAG` |
| New persistent severe headache without emergency red flags | `same_day_review` | `source_backed_needs_medical_review` | `HEADACHE_NEW_SEVERE_REVIEW` |
| Chronic stable mild headache without red flags | `prompt_clinical_review` or `monitor_with_safety_net` | `needs_source` | `HEADACHE_STABLE_NEEDS_SOURCE` |

Unsafe wording to avoid:

- "Headaches are usually harmless" when red flags are present.
- "Take painkillers and wait" for thunderclap headache.
- "This is definitely migraine."
- "No weakness means no emergency."

Implementation notes for `risk_rules.yaml`:

- Current `SUDDEN_SEVERE_HEADACHE` requires sudden onset plus an OR neurological feature. Rulebook should add thunderclap/worst-headache as emergency even before other features are confirmed.
- Add fields for `thunderclap_headache`, `worst_headache`, `neck_stiffness`, `fever`, `vomiting`, `headache_after_head_injury`.

Source citations:

- CDC stroke signs and symptoms: https://www.cdc.gov/stroke/signs-symptoms/index.html
- NHS headaches: https://www.nhs.uk/conditions/headaches/
- NHS subarachnoid haemorrhage: https://www.nhs.uk/conditions/subarachnoid-haemorrhage/
- CDC TBI danger signs: https://www.cdc.gov/traumatic-brain-injury/signs-symptoms/index.html

### 8. Tremor / Parkinsonian Movement Signs

`requires_medical_review: true`

Symptom family name: tremor / parkinsonian movement signs.

Key user phrases:

- Chinese: "手抖", "震颤", "静止时抖", "动作变慢", "走路拖步", "小碎步", "身体僵硬", "面具脸", "写字变小".
- English: "tremor", "shaking hands", "resting tremor", "slowness", "stiffness", "shuffling gait", "small handwriting", "masked face", "Parkinson's signs".

Red-flag features:

- Sudden unilateral weakness/numbness, facial droop, speech change, vision change, severe headache, acute confusion, seizure, or loss of consciousness: handle under stroke/emergency families, not routine tremor.
- Rapid worsening with falls, inability to walk, hallucinations, severe medication side effects, or acute confusion.
- New or progressive tremor with slowness, rigidity, gait change, falls, or functional impact.

Missing critical fields to ask:

- Sudden vs gradual; resting vs action tremor.
- One side or both; new vs longstanding.
- Slowness, stiffness, shuffling gait, falls, freezing, handwriting change.
- Medication changes, caffeine/stimulants, alcohol withdrawal, thyroid symptoms if known.
- Hallucinations, confusion, sleep disturbance.
- Functional impact: eating, dressing, walking, writing.

Action-tier mapping:

| Condition | Action tier | evidence_status | Reason codes |
| --- | --- | --- | --- |
| Tremor with stroke-like sudden focal signs | `emergency_now` | `source_backed_by_stroke_sources` | `TREMOR_WITH_STROKE_RED_FLAG` |
| Tremor/parkinsonism with acute confusion, fall injury, or inability to walk | `same_day_review` or `emergency_now` depending red flag | `source_backed_needs_medical_review` | `PARKINSONISM_ACUTE_SAFETY_RISK` |
| New or progressive tremor with slowness/stiffness/gait change | `prompt_clinical_review` | `source_backed` | `TREMOR_PARKINSONISM_REVIEW` |
| Longstanding stable mild tremor without disability or red flags | `prompt_clinical_review` or `monitor_with_safety_net` | `needs_source` | `TREMOR_STABLE_NEEDS_SOURCE` |

Unsafe wording to avoid:

- "This is definitely Parkinson's disease."
- "Tremor is normal aging."
- "No need to mention falls."
- "Stop or change medication" unless instructed by a clinician.

Implementation notes for `risk_rules.yaml`:

- Current `TREMOR_PROGRESSIVE` is directionally aligned with prompt clinical review.
- Add flags for `resting_tremor`, `bradykinesia_or_slowness`, `rigidity`, `shuffling_gait`, `functional_impact`.
- Keep tremor-specific rules below emergency stroke/head-injury/seizure rules.

Source citations:

- NHS Parkinson's disease symptoms: https://www.nhs.uk/conditions/parkinsons-disease/symptoms/
- NICE Parkinson's disease guideline NG71: https://www.nice.org.uk/guidance/ng71/chapter/Recommendations
- NINDS Parkinson's disease: https://www.ninds.nih.gov/health-information/disorders/parkinsons-disease

### 9. Memory Decline / Cognitive Decline

`requires_medical_review: true`

Symptom family name: memory decline / cognitive decline.

Key user phrases:

- Chinese: "记忆力下降", "老忘事", "找不到路", "重复问同样问题", "不会做熟悉的事", "认不出人", "叫不出名字", "找词困难", "认知下降".
- English: "memory decline", "forgetting things", "repeating questions", "getting lost", "trouble with familiar tasks", "word-finding difficulty", "cognitive decline", "possible dementia".

Red-flag features:

- Sudden confusion or altered awareness: treat as acute confusion/delirium emergency.
- New focal neurological signs, speech/language trouble, vision change, severe headache, seizure, loss of consciousness, or head injury.
- Rapid decline over days/weeks, safety risks, wandering, medication errors, inability to manage food/fluids, or self-neglect.
- Progressive memory/cognitive symptoms affecting daily function.

Missing critical fields to ask:

- Acute change vs gradual months/years.
- Functional impact: medications, finances, cooking, driving, getting lost.
- Orientation: person/place/time.
- Fluctuation, hallucinations, sleep disturbance, movement signs.
- Mood symptoms, depression, alcohol/substance, medication changes.
- Safety risk: wandering, leaving stove on, falls.
- Caregiver observations and baseline.

Action-tier mapping:

| Condition | Action tier | evidence_status | Reason codes |
| --- | --- | --- | --- |
| Sudden confusion/altered awareness | `emergency_now` | `source_backed` | `COGNITIVE_ACUTE_CONFUSION_EMERGENCY` |
| Cognitive change with stroke/head injury/seizure/severe headache red flags | `emergency_now` | `source_backed` | `COGNITIVE_WITH_NEURO_RED_FLAG` |
| Rapid decline over days/weeks or major safety risk | `same_day_review` | `source_backed_needs_medical_review` | `COGNITIVE_RAPID_OR_SAFETY_RISK` |
| Gradual memory/cognitive decline affecting function | `prompt_clinical_review` | `source_backed` | `MEMORY_DECLINE_REVIEW`, `DEMENTIA_ASSESSMENT_REVIEW` |
| Mild stable forgetfulness without functional impairment and no red flags | `monitor_with_safety_net` plus routine review if concerned | `source_backed_needs_medical_review` | `MEMORY_MILD_STABLE_SAFETY_NET` |

Unsafe wording to avoid:

- "This is normal aging."
- "It is definitely dementia."
- "Nothing can be done."
- "Memory loss is not urgent" when it is sudden, rapid, or unsafe.

Implementation notes for `risk_rules.yaml`:

- Current `COGNITIVE_DECLINE_ACUTE` name conflicts with its rule description "weeks to months"; rename to avoid confusing acute delirium with progressive cognitive decline.
- Add `functional_impairment`, `rapid_decline_days_weeks`, `safety_risk`, `wandering`, `medication_errors`, and `baseline_dementia`.
- Keep acute confusion emergency rules separate from dementia/memory review rules.

Source citations:

- NHS dementia symptoms: https://www.nhs.uk/conditions/dementia/symptoms-and-diagnosis/symptoms/
- NHS dementia diagnosis: https://www.nhs.uk/conditions/dementia/symptoms-and-diagnosis/diagnosis/
- NICE dementia guideline NG97: https://www.nice.org.uk/guidance/ng97/chapter/Recommendations
- WHO dementia fact sheet: https://www.who.int/news-room/fact-sheets/detail/dementia
- National Institute on Aging cognitive health: https://www.nia.nih.gov/health/brain-health/cognitive-health-and-older-adults

### 10. Mood/behavior/personality Change

`requires_medical_review: true`

Symptom family name: mood, behavior, or personality change.

Key user phrases:

- Chinese: "性格变了", "脾气突然变差", "突然很激动", "变得冷漠", "不爱说话", "行为怪异", "疑神疑鬼", "幻觉", "想伤害自己", "想自杀", "想伤害别人".
- English: "personality changed", "new agitation", "apathy", "withdrawn", "disinhibited", "paranoid", "hallucinations", "behavior change", "suicidal", "self-harm", "might hurt someone".

Red-flag features:

- Immediate danger to self or others, suicidal intent, self-harm, violence risk.
- Sudden confusion, altered awareness, hallucinations with acute onset, seizure, head injury, stroke signs, severe headache.
- Rapid behavior/personality change, especially with cognitive decline or neurological symptoms.
- New hallucinations, delusions, marked agitation, wandering, unsafe behavior.

Missing critical fields to ask:

- Any immediate risk of self-harm, suicide, harm to others, or inability to stay safe.
- Sudden vs gradual; hours/days vs weeks/months.
- Confusion, awareness change, hallucinations, delusions.
- Medication/substance changes, infection symptoms, sleep deprivation.
- Cognitive decline, falls, movement signs, head injury, stroke symptoms.
- Caregiver safety and supervision.

Action-tier mapping:

| Condition | Action tier | evidence_status | Reason codes |
| --- | --- | --- | --- |
| Immediate danger to self/others or suicidal intent | `emergency_now` / crisis line plus emergency services when imminent | `source_backed` | `SELF_HARM_IMMEDIATE_DANGER`, `HARM_TO_OTHERS_IMMEDIATE_DANGER` |
| Behavior/personality change with sudden confusion, altered awareness, stroke signs, seizure, head injury, severe headache | `emergency_now` | `source_backed` | `BEHAVIOR_WITH_NEURO_EMERGENCY` |
| New hallucinations/delusions/agitation with safety risk | `same_day_review` or `emergency_now` depending immediate danger | `source_backed_needs_medical_review` | `BEHAVIOR_SAFETY_RISK` |
| Gradual personality/behavior change with cognitive decline or parkinsonian signs | `prompt_clinical_review` | `source_backed` | `PERSONALITY_COGNITIVE_REVIEW`, `BEHAVIOR_PARKINSONISM_REVIEW` |

Unsafe wording to avoid:

- "It is just personality."
- "Ignore hallucinations if they are not scary."
- "They are doing it on purpose."
- "This is definitely dementia/psychiatric."
- "Do not call for help" when there is self-harm or violence risk.

Implementation notes for `risk_rules.yaml`:

- Current `PERSONALITY_BEHAVIOR_CHANGE` is medium risk but does not separate imminent self-harm/violence from gradual cognitive/behavioral change.
- Add fields for `self_harm_intent`, `suicidal_ideation`, `harm_to_others_risk`, `unsafe_behavior`, `acute_hallucinations`, `delusions`, and `caregiver_safety_risk`.
- Route immediate danger through crisis/emergency templates as well as neurological emergency logic.

Source citations:

- NHS sudden confusion: https://www.nhs.uk/conditions/confusion/
- NHS dementia symptoms: https://www.nhs.uk/conditions/dementia/symptoms-and-diagnosis/symptoms/
- NHS dementia diagnosis: https://www.nhs.uk/conditions/dementia/symptoms-and-diagnosis/diagnosis/
- WHO dementia fact sheet: https://www.who.int/news-room/fact-sheets/detail/dementia
- NIMH suicide prevention: https://www.nimh.nih.gov/health/topics/suicide-prevention
- SAMHSA 988 Lifeline: https://www.samhsa.gov/find-help/988

## Source Bibliography

Stroke and acute neurological warning signs:

- CDC. Stroke Signs and Symptoms. https://www.cdc.gov/stroke/signs-symptoms/index.html
- American Stroke Association. Stroke Symptoms and F.A.S.T. https://www.stroke.org/en/about-stroke/stroke-symptoms
- NHS. Stroke - Symptoms. https://www.nhs.uk/conditions/stroke/symptoms/
- NINDS. Stroke. https://www.ninds.nih.gov/health-information/disorders/stroke

Confusion/delirium:

- NHS. Confusion. https://www.nhs.uk/conditions/confusion/
- NICE. Delirium: prevention, diagnosis and management in hospital and long-term care, CG103. https://www.nice.org.uk/guidance/cg103/chapter/Recommendations

Seizure/loss of consciousness:

- CDC. First Aid for Seizures. https://www.cdc.gov/epilepsy/first-aid-for-seizures/index.html
- NHS. What to do if someone has a seizure. https://www.nhs.uk/conditions/what-to-do-if-someone-has-a-seizure-fit/
- NICE. Transient loss of consciousness in over 16s, CG109. https://www.nice.org.uk/guidance/cg109/chapter/Recommendations

Falls/head injury:

- CDC. Traumatic Brain Injury Signs and Symptoms. https://www.cdc.gov/traumatic-brain-injury/signs-symptoms/index.html
- NHS. Head injury and concussion. https://www.nhs.uk/conditions/head-injury-and-concussion/
- NICE. Falls: assessment and prevention in older people and in people 50 and over at higher risk, NG249. https://www.nice.org.uk/guidance/ng249/chapter/Recommendations
- CDC. Older Adult Fall Prevention. https://www.cdc.gov/falls/older-adult-falls/index.html

Vision/headache:

- NHS. Vision loss. https://www.nhs.uk/conditions/vision-loss/
- National Eye Institute. Eye Health Emergencies. https://www.nei.nih.gov/learn-about-eye-health/healthy-vision/eye-health-emergencies
- NHS. Headaches. https://www.nhs.uk/conditions/headaches/
- NHS. Subarachnoid haemorrhage. https://www.nhs.uk/conditions/subarachnoid-haemorrhage/

Parkinsonism, dementia, mood/behavior:

- NHS. Parkinson's disease symptoms. https://www.nhs.uk/conditions/parkinsons-disease/symptoms/
- NICE. Parkinson's disease in adults, NG71. https://www.nice.org.uk/guidance/ng71/chapter/Recommendations
- NINDS. Parkinson's Disease. https://www.ninds.nih.gov/health-information/disorders/parkinsons-disease
- NHS. Dementia symptoms and diagnosis. https://www.nhs.uk/conditions/dementia/symptoms-and-diagnosis/
- NICE. Dementia: assessment, management and support, NG97. https://www.nice.org.uk/guidance/ng97/chapter/Recommendations
- WHO. Dementia fact sheet. https://www.who.int/news-room/fact-sheets/detail/dementia
- National Institute on Aging. Cognitive Health and Older Adults. https://www.nia.nih.gov/health/brain-health/cognitive-health-and-older-adults
- NIMH. Suicide Prevention. https://www.nimh.nih.gov/health/topics/suicide-prevention
- SAMHSA. 988 Suicide & Crisis Lifeline. https://www.samhsa.gov/find-help/988
