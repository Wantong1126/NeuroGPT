# NeuroGPT v2 — Execution Progress Tracker

> Updated after each phase/step completion.
> MaxClaw restart: read this file first to resume.

## Phase 0 — Repo Normalization
- Status: ✅ COMPLETE
- Commit: `1170475`
- Completed: 2026-03-22
- Steps done: Directory restructure, canonical types (core/types.py), pipeline/, modules/, knowledge/, tests/, ui/, archived modes/ + router.py

## Phase 1 — No-RAG MVP Pipeline
- Status: 🔄 IN PROGRESS
- Goal: Full end-to-end runnable pipeline, no retrieval needed

### Steps (Executive Plan Section 12):
- [ ] Step 1.1: modules/symptom_extractor.py — place in modules/ ✅ (copied from core/)
- [ ] Step 1.2: modules/question_manager.py — ✅ DONE (configs/question_rules.yaml to be added)
- [ ] Step 1.3: modules/concern_estimator.py — ✅ DONE (wraps risk_stratifier)
- [ ] Step 1.4: modules/action_mapper.py — ✅ DONE
- [ ] Step 1.5: modules/hesitation_detector.py — ✅ DONE
- [ ] Step 1.6: modules/response_builder.py — ✅ DONE
- [ ] Step 1.7: modules/summary_generator.py — ⚠️  PENDING (API key needed for LLM)
- [ ] Step 1.8: pipeline/orchestrator.py — ✅ DONE
- [ ] TEST: End-to-end CLI run — ⚠️  PENDING (API key needed for steps that call LLM)

### Blockers for Phase 1:
- API key needed for: symptom_extractor (LLM call), summary_generator (LLM call)
- Stub implementations exist for all LLM-dependent functions

## Phase 2 — Multi-Turn Memory
- Status: ⬜ NOT STARTED
- Steps: conversation_memory.py, orchestrator multi-turn merge

## Phase 3 — Minimal Retrieval Support
- Status: ⬜ NOT STARTED
- Note: retrieval.yaml enabled=false in Phase 1
- Steps: source_registry, chunker, ingest, retriever stubs all exist

## Phase 4 — UI Refinement
- Status: ⬜ NOT STARTED
- Steps: ui/app.py CLI stub exists

## Phase 5 — Evaluation and Hardening
- Status: ⬜ NOT STARTED
- Note: requires test scenarios across stroke, parkinson, delirium, hesitation patterns

## Key Files Reference
- Entry point: ui/app.py
- Pipeline: pipeline/orchestrator.py
- State: pipeline/state.py
- Types: core/types.py
- Risk engine: core/risk_stratifier.py + configs/risk_rules.yaml
- Hesitation: configs/hesitation_patterns.yaml
- References: docs/REFERENCES.md

## Restart Recovery
After MaxClaw restart:
1. Read this file (PROGRESS.md)
2. Check git log --oneline for last completed phase
3. Read the relevant module stubs and continue from next uncompleted step
