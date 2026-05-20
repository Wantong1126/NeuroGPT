Extract normalized symptom observations from this user text.

User text:
{user_input}

Rules:
- Return observations only.
- Do not output concern_level, action_level, diagnosis, triage advice, or care recommendations.
- Use the exact user wording in evidence_text.
- Use unknown for onset, duration, laterality, progression, or severity when the user did not state it.
- Use possible for everyday or ambiguous symptoms.
- Use red_flag_candidate when a symptom may become urgent only after onset/laterality/duration/context is clarified.
- Use true_red_flag only when the wording itself clearly supports it.
