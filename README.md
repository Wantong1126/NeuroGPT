# NeuroGPT

NeuroGPT v1 is a Flask web product for elder care status reporting, staff confirmation, family reports, and institution overview.

The current release establishes the product shell while preserving the existing deterministic-first care pipeline. Database storage, authentication, voice input, generated reports, and advanced interface workflows are outside this release.

## Product surfaces

- **Elder:** a simple check-in for reporting changes, discomfort, or concerns.
- **Staff:** a workflow for reviewing and confirming resident updates.
- **Family:** confirmed, family-facing resident status reports.
- **Institution:** an overview for institution activity and resident tracking.

## Architecture

```text
elder input
    -> AI follow-up / CaseState
    -> staff confirmation
    -> family report
    -> institution tracking
```

The implemented elder flow uses the existing `CaseState` and `run_pipeline()` path for symptom extraction, follow-up questions, concern and action mapping, caregiver summaries, and available care-home handoff/report items. The later workflow stages are product placeholders in this release.

## Install and run

```bash
python -m pip install -r requirements.txt
python web_app.py
```

Open `http://127.0.0.1:5000/`.

## Flask routes

- `GET /` — product home and role entry
- `GET /elder` — elder check-in
- `POST /elder/report` — process an elder update through `run_pipeline()`
- `GET /staff` — staff confirmation area
- `GET /family` — confirmed family reports
- `GET /admin` — institution overview
- `POST /reset` — reset the current elder session

## Session and pipeline behavior

Flask stores the current session identifier in the signed browser cookie. The corresponding `CaseState` is stored as JSON in `.sessions/`. Each elder report loads that state, passes the new input through `run_pipeline()`, and saves the updated state for follow-up turns.

Resident and care-event product records are stored separately under `.product_data/`. The file-backed interface in `core/product_store.py` keeps product workflow storage independent from pipeline session state and can later be replaced by a database-backed implementation.

Key implementation files:

- `web_app.py` — Flask entrypoint
- `ui/web.py` — product routes
- `core/session.py` — file-backed session persistence
- `core/product_store.py` — resident and care-event storage
- `pipeline/orchestrator.py` — shared pipeline entrypoint

## Tests

```bash
python -m pytest tests/ -v --tb=short
```
