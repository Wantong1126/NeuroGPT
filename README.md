# NeuroGPT

NeuroGPT is a deterministic-first neurology triage prototype for older adults and caregivers.
The current runnable product is a CLI demo, not a web UI.

## Current Status

- Phase 4 status: CLI demo only
- No Flask routes or browser UI are implemented in this repository
- The main runnable entrypoint is `python app.py`
- LLM-backed extraction is optional and requires an API key; without one the project uses a heuristic fallback

## Requirements

Install the project dependencies:

```bash
python -m pip install -r requirements.txt
```

Runtime/test dependencies currently required by the codebase:

- `pydantic`
- `PyYAML`
- `httpx`
- `pytest`

## Run The CLI Demo

Start the interactive CLI:

```bash
python app.py
```

You can then type symptom descriptions turn by turn. Enter `exit` to quit.

The CLI entrypoints are:

- [app.py](/d:/Project_NeuroGPT/NeuroGPT/NeuroGPT/app.py)
- [ui/app.py](/d:/Project_NeuroGPT/NeuroGPT/NeuroGPT/ui/app.py)

## Run Tests

Run the full test suite:

```bash
python -m pytest tests/ -v --tb=short
```

## End-to-End Dry Run

For a quick end-to-end dry run from Python:

```bash
python - <<'PY'
from pipeline.orchestrator import run_pipeline
state, output = run_pipeline("demo-session", "sudden left arm weakness with slurred speech this morning")
print(output.model_dump_json(indent=2))
PY
```

If you want turn-by-turn behavior, use the CLI demo instead of the one-shot snippet above.

## Optional LLM Configuration

LLM mode is only used when these environment variables are set:

- `NEUROGPT_LLM_API_KEY`
- `NEUROGPT_LLM_BASE_URL`
- `NEUROGPT_LLM_MODEL`

Without those variables, symptom extraction falls back to heuristic parsing.
