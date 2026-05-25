Extract normalized symptom observations from this user text.

User text:
{user_input}

Rules:
- Return observations only.
- Return one JSON object with exactly one top-level key: observations.
- Do not output extra fields outside the observation schema.
- Do not output action_level, concern_level, diagnosis, urgency, triage advice, care setting, or care recommendations anywhere.
- Do not decide urgency, risk, concern level, action level, diagnosis, or care setting. Your task is observation extraction only.
- Every enum field must use exactly one of the allowed values listed below. Do not invent synonyms, categories, or aliases.
- Use only these symptom_family values: weakness, facial_asymmetry, sensory, speech_language, confusion_awareness, memory_cognitive, gait_balance, headache, vision, seizure_episode, loss_of_consciousness, fall_head_injury, fatigue, other.
- Never use "unknown" as symptom_family. Use other for vague symptoms that do not fit a listed family.
- Use only these signal_strength values: possible, red_flag_candidate, true_red_flag.
- Use only these onset values: sudden, gradual, chronic, unknown.
- Use only these duration_category values: transient_resolved, minutes_hours, days, weeks_months, years_chronic, unknown.
- Use only these laterality values: one_side, both_sides, central, unknown.
- Use only these progression values: first_time, worsening, stable, improving, recurring, unknown.
- Use only these severity_qualifier values: mild, moderate, severe, unknown.
- confidence must be a JSON number from 0.5 to 1.0 when an observation is included. Do not use strings, null, percentages, words, or values below 0.5.
- If confidence would be below 0.5, do not output that observation.
- evidence_text must be copied exactly from the user input. Do not paraphrase, translate, summarize, normalize punctuation, or add words.
- Do not output an observation unless its evidence_text is a contiguous substring present in the user input.
- Do not output evidence_text that describes meaning instead of quoting the user text.
- Use unknown for onset, duration, laterality, progression, or severity when the user did not state it.
- Use possible for everyday or ambiguous symptoms.
- Use red_flag_candidate when a symptom may become urgent only after onset/laterality/duration/context is clarified.
- Use true_red_flag only when the wording itself clearly supports it.
- If wording is ambiguous, set clarification_needed=true, explain briefly in clarification_reason, use symptom_family=other when no single family is directly supported, and list possible_families instead of forcing one family.
- For ambiguous lay descriptions such as "weird", "not right", "not obeying", "not flexible", "stuck", "strange", "off", or "cannot say what is wrong", do not invent unsupported symptom families. Use symptom_family=other, possible_families with only allowed symptom_family values, and clarification_needed=true.
- possible_families may contain only allowed symptom_family values. Never include unknown, motor, neurologic, unclear, or any other value not listed above.
- Do not set clarification_needed=true for clear emergency clusters when symptom family and onset are already clear, such as sudden one-sided weakness/facial asymmetry, seizure followed by cannot wake, sudden speech change, sudden vision loss, or head injury with confusion.
- Do not infer onset, duration, laterality, progression, severity, or associated red flags unless supported by exact wording in the user input.
- Use empty arrays for associated_red_flags and possible_families when none are supported. Do not use null.
- Use empty strings for duration_text and clarification_reason when not applicable. Do not use null.
- Output only fields in the observation schema. If a field is not in the schema, omit it.
