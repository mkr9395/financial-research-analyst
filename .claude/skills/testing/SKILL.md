---
name: testing
description: Testing conventions for this project using pytest markers unit, integration, e2e and live. Use when writing, running, or fixing tests.
---

# Testing

## Markers (registered in `pytest.ini`)
- `unit`: fast, no network, no real LLM.
- `integration`: multiple components together; models and APIs stubbed.
- `e2e`: full agent run.
- `live`: calls real APIs (OpenAI, Tavily). Skipped automatically by `tests/conftest.py` when the required keys are missing. Always combine with another marker, e.g. `@pytest.mark.live` plus `@pytest.mark.e2e`.

## Commands
- Default (offline): `python -m pytest -m "not live"`
- One level: `python -m pytest -m unit`
- Live: `python -m pytest -m live`

## Rules
- Tests live in `tests/` and mirror `app/` modules.
- Never put key values in tests or fixtures. Check only whether a key is set.
- Prefer fakes/stubs over mocking internals; keep unit tests deterministic.
- Report failures with the actual output; do not claim a pass without running.
