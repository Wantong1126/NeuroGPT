# OpenAI Live Observation Eval Review

## Reports reviewed

- `reports/live_eval_gpt-5.4-mini_smoke.md`
- `reports/live_eval_gpt-5.4-mini_ambiguous.md`
- `reports/live_eval_gpt-5.4-mini_full.md`
- `reports/observation_eval_report.md`
- `reports/live_observation_eval_report.md`
- `reports/live_eval/model_comparison.md`
- `docs/llm_eval.md`
- `scripts/eval_observation_extraction.py`

The older `reports/live_observation_eval_report.md` and `reports/live_eval/*` smoke comparison artifacts were skipped/no-key reports and are not evidence of real OpenAI model performance.

## Model evaluated

- Provider: `openai_compatible`
- Model: `gpt-5.4-mini`
- Live eval ran: yes, in the smoke, ambiguous, and full reports.

## Live LLM metrics

These rows summarize the `live_llm` section, not deterministic or mocked fixture results.

| report | cases | report verdict | schema_valid_rate | evidence_grounded_rate | expected_family_match_rate | acceptable_family_match_rate | clarification_needed_match_rate | hallucinated_observation_count | unsafe_action_override_count | emergency_preservation_rate | overmedicalization_failure_count | ambiguous_case_overconfidence_count |
| --- | ---: | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| smoke | 8 | FAIL | 1.000 | 0.000 | 0.000 | 0.000 | 0.250 | 0 | 0 | 0.000 | 0 | 0 |
| ambiguous | 8 | PARTIAL | 1.000 | 0.000 | n/a | 0.000 | 1.000 | 0 | 0 | n/a | 0 | 0 |
| full | 32 | FAIL | 1.000 | 0.000 | 0.000 | 0.000 | 0.500 | 0 | 0 | 0.000 | 0 | 0 |

## Merged-path note

The `live_merged` section passed the safety gates in the smoke and full reports, but this appears to be because deterministic observations preserved the pipeline behavior. The raw `live_llm` rows show empty accepted observation families across all live cases. Therefore the merged PASS should not be interpreted as the OpenAI model independently passing observation extraction.

## Failed cases summary

- Smoke `live_llm`: all 8 live cases failed. The six clear red-flag cases failed expected/acceptable family matching, evidence grounding, clarification, emergency preservation, and context checks. The two missing-info cases failed family matching, evidence grounding, and context where applicable.
- Ambiguous `live_llm`: all 8 ambiguous lay-description cases failed acceptable family matching and evidence grounding. Clarification behavior matched, and there was no ambiguous overconfidence.
- Full `live_llm`: all 32 cases failed evidence grounding. Expected and acceptable family matching were 0.000, emergency preservation was 0.000, and every case had empty accepted observation families.
- No unsafe action override was detected in live model outputs.
- No overmedicalization failure or ambiguous overconfidence was detected, but this is not enough to offset the complete extraction failure.

## Safety verdict

For raw live LLM observation extraction, the OpenAI candidate should be classified as FAIL for NeuroGPT observation extraction at this stage.

Reasoning:

- It did not meet `evidence_grounded_rate >= 0.95`.
- It did not preserve emergencies in the raw live LLM path.
- It produced no accepted observation families in the live LLM rows.
- Schema validity was acceptable and there were no action-tier override attempts, but the extracted observations were not usable.

## Recommendation

Proceed to DeepSeek live eval comparison only as an evaluation step, not because OpenAI passed. The OpenAI candidate should not be promoted, selected as default, or treated as clinically validated. DeepSeek should be run through the same smoke, ambiguous, and full report flow to determine whether this failure is model-specific or a shared prompt/schema compatibility issue.

If DeepSeek shows similar empty-observation behavior, adjust the prompt/schema or parser expectations before comparing further models.

## Remaining limitations

- Reports are Markdown summaries; raw model JSON was not reviewed here.
- The `schema_valid_rate` only confirms that an observations list was present, not that parsed observations were useful.
- The `live_merged` PASS demonstrates deterministic fallback safety, not independent LLM extraction quality.
- This review does not change product logic and does not validate any model for diagnosis, medical advice, care setting, or action-tier control.
