# NeuroGPT

NeuroGPT is a deterministic-first neurology triage prototype for older adults and caregivers.
The project now has two runnable surfaces that share the same pipeline:

- CLI demo
- Minimal Flask web demo

The underlying pipeline remains the same `CaseState -> extract -> follow-up -> concern -> action -> response -> caregiver summary` flow.

## Runtime Status

- CLI: runnable
- Flask: runnable
- Symptom extractor: provider-switchable, defaults to heuristic fallback
- Summary generator: provider-switchable, defaults to heuristic fallback
- RAG content: not implemented yet
- Safety hook extensions: not implemented yet

## Install

```bash
python -m pip install -r requirements.txt
```

Current dependencies in [requirements.txt](/d:/Project_NeuroGPT/NeuroGPT/NeuroGPT/requirements.txt):

- `Flask`
- `pydantic`
- `PyYAML`
- `httpx`
- `pytest`

## CLI Entrypoint

CLI entrypoint files:

- [app.py](/d:/Project_NeuroGPT/NeuroGPT/NeuroGPT/app.py)
- [ui/app.py](/d:/Project_NeuroGPT/NeuroGPT/NeuroGPT/ui/app.py)

Run the CLI demo:

```bash
python app.py
```

The CLI keeps the active `CaseState` in memory for the current process and updates it turn by turn.

## Flask Entrypoint

Flask entrypoint files:

- [web_app.py](/d:/Project_NeuroGPT/NeuroGPT/NeuroGPT/web_app.py)
- [ui/web.py](/d:/Project_NeuroGPT/NeuroGPT/NeuroGPT/ui/web.py)
- [ui/templates/index.html](/d:/Project_NeuroGPT/NeuroGPT/NeuroGPT/ui/templates/index.html)

Run the Flask demo:

```bash
python web_app.py
```

Then open:

```text
http://127.0.0.1:5000/
```

Available routes:

- `GET /` renders the current session view
- `POST /chat` submits the next user turn
- `POST /reset` deletes the active session and starts over

## How Session / CaseState Persistence Works

CLI:

- `CaseState` is kept in memory inside the running CLI process.

Flask:

- Flask stores only the `session_id` in the signed browser session cookie.
- The actual `CaseState` is persisted on disk as JSON files in `.sessions/`.
- The storage helpers live in [core/session.py](/d:/Project_NeuroGPT/NeuroGPT/NeuroGPT/core/session.py).
- Each `/chat` request loads the current `CaseState`, runs `run_pipeline()`, then saves the updated state back to disk.

Shared pipeline entrypoint:

- [pipeline/orchestrator.py](/d:/Project_NeuroGPT/NeuroGPT/NeuroGPT/pipeline/orchestrator.py)

## Provider Switching

Provider switching is config-driven.

Config file:

- [configs/providers.yaml](/d:/Project_NeuroGPT/NeuroGPT/NeuroGPT/configs/providers.yaml)

Config helper:

- [core/provider_settings.py](/d:/Project_NeuroGPT/NeuroGPT/NeuroGPT/core/provider_settings.py)

Current supported provider values:

- `heuristic`
- `openai_compatible`

Current default config:

- `symptom_extractor.provider = heuristic`
- `summary_generator.provider = heuristic`

Activation points:

- [modules/symptom_extractor.py](/d:/Project_NeuroGPT/NeuroGPT/NeuroGPT/modules/symptom_extractor.py)
- [modules/summary_generator.py](/d:/Project_NeuroGPT/NeuroGPT/NeuroGPT/modules/summary_generator.py)
- [core/llm.py](/d:/Project_NeuroGPT/NeuroGPT/NeuroGPT/core/llm.py)

Behavior:

- If provider is `heuristic`, the module stays local and deterministic/stubbed.
- If provider is `openai_compatible`, the module attempts an LLM call through `core.llm`.
- If the live call fails or no API key is configured, the module falls back to the heuristic path.

## What Is Live vs Stub

Live now:

- deterministic concern estimation
- action mapping
- hesitation detection
- multi-turn state merge
- CLI demo
- Flask demo
- file-backed session persistence for Flask

Stub / fallback now:

- live GPT symptom extraction is prepared but not active by default
- live GPT caregiver summary generation is prepared but not active by default
- knowledge retrieval / RAG content is not wired in yet

## Tests

Run the full test suite:

```bash
python -m pytest tests/ -v --tb=short
```

This now includes:

- concern estimator tests
- hesitation detector tests
- scenario matrix regression tests
- Flask route/session persistence tests

## Demo Flow Validation

A small demo-ready validation script is available at:

- [scripts/demo_flows.py](/d:/Project_NeuroGPT/NeuroGPT/NeuroGPT/scripts/demo_flows.py)

Run it with:

```bash
python scripts/demo_flows.py
```

It validates:

- single-turn high-risk escalation
- multi-turn merge
- hesitation handling
- caregiver summary output
