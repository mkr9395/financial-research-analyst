---
name: testing
description: Testing approach for this project. Explains unit, integration and end-to-end tests, the pytest markers unit/integration/e2e/live, mocking the model and Tavily, failure testing, and regression testing. Use when writing, running, or fixing tests.
---

# Testing

## Test levels
- **Unit** (`@pytest.mark.unit`): one function or module in isolation. No network, no real LLM, no real filesystem outside `tmp_path`. Examples: report rendering from a `ResearchReport`, date injection into prompts, subagent config shape, path handling, Pydantic validation.
- **Integration** (`@pytest.mark.integration`): several components together with external services stubbed. Examples: the agent builds with the real `subagents.py` and a fake model; a tool plus its schema; the backend confined to a temp workspace; the interrupt/resume flow with a fake model and an in-memory checkpointer.
- **End-to-end** (`@pytest.mark.e2e`): a full agent run on a request. Few, slow, and normally also `live`.
- **Live** (`@pytest.mark.live`): calls real APIs (OpenAI, Tavily). `tests/conftest.py` skips them automatically when `OPENAI_API_KEY` or `TAVILY_API_KEY` is unset (presence check only). Combine with another marker, e.g. `live` + `e2e`.

All four markers are registered in `pytest.ini`; do not add unregistered markers.

## Commands
- Offline: `python -m pytest -m "not live"`
- One level: `python -m pytest -m unit`
- Live: `python -m pytest -m live`
- Single failing test first: `python -m pytest path::test_name -x`

## Mocking the model
- Replace the chat model with a fake that returns scripted messages (including tool calls). Check what the installed `langchain-core` offers (e.g. fake or generic fake chat models) before writing your own: verify, do not assume.
- Inject the model through the agent factory (a parameter), not by patching globals.
- Scripted responses let you assert delegation (`task` called with the right `subagent_type`), that todos are written, and that the final structured output validates.
- Never put a real model name or key in test code.

## Mocking Tavily
- Hide the search behind one tool function and substitute a stub returning canned results (a realistic dict/list shaped like the real tool output; verify the shape from the installed package).
- Cover: normal results, empty results, and an upstream error.
- Use `monkeypatch` or constructor injection; no real HTTP in non-live tests.

## Failure testing
Test that failures are loud and handled correctly, not hidden:
- Missing or invalid environment configuration (no `MODEL`, no keys) gives a clear error.
- Tavily errors, timeouts and empty results propagate as meaningful tool errors the agent can see.
- Invalid structured output is rejected by Pydantic validation (`pytest.raises`).
- Path escape attempts (`..`, absolute paths outside `workspace/`) are blocked.
- Human rejection of `submit_draft_assessment` leads to revision, not a final report.
- Recursion limit exceeded surfaces the real error.
- Do not use broad `except Exception` in code to make a test pass.

## Regression testing
- Every fixed bug gets a test that fails before the fix and passes after, named for the bug.
- Keep the offline suite fast and deterministic so it runs every session.
- Pin behavior that is easy to break: the report schema, prompt contents (date present, paths mentioned), the list of subagents and their names, and `pytest.ini` markers.
- Before finishing a session, run the whole offline suite, not just the new tests.

## Rules
- Tests live in `tests/` and mirror `app/`.
- No secret values in tests, fixtures, or output; only check whether keys are set.
- Use `tmp_path` for any workspace used in tests; never write into the real `workspace/`.
- Report exact results (passed, failed, skipped) and never claim a pass without running the tests.
