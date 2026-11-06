# Dev log

## Session 1 - Project foundation

**Built**
- Environment check: Python 3.11.9, `.venv` active, git repo on `main`; no project packages installed.
- Project structure: `app/`, `tests/`, `workspace/` (skills, memories committed; research, reports git-ignored), `docs/`, `.claude/`.
- `.claude/settings.json` denying reads of `.env`; Claude Code skills `deep-agent-development` and `testing`; read-only subagent `architecture-reviewer` (classifies findings MUST FIX / SHOULD FIX / POC ACCEPTABLE / PRODUCTION ONLY).
- `CLAUDE.md` (purpose, scope, architecture, fixed design decisions, standards, security, testing, workflow, debugging protocol, end-of-session procedure).
- `docs/architecture.md` (manager, three specialists, search tool, skills, workspace layout, memory, approval tool, structured output, LangSmith).
- `pytest.ini` with markers unit/integration/e2e/live; `tests/conftest.py` auto-skipping `live` tests when keys are missing; `.env.example`; unpinned `requirements.txt`.

**Key decisions and why**
- Single `FilesystemBackend` rooted at `workspace/` with `virtual_mode=True`: docs state that without it there is no real path confinement.
- Orchestration only via built-in Deep Agents features (`task`, todos, `interrupt_on`); no custom graph or middleware, to keep the POC small.
- Human approval through `interrupt_on` on `submit_draft_assessment` with a checkpointer, not `input()`.
- Three specialists (Financial Researcher, Industry Researcher, Risk Analyst), each writing `/research/<area>.md` and returning a short summary.
- `.env` protected by a `Read` deny rule (Bash deny rules are best-effort only).
- Dev skills (`.claude/skills/`) kept separate from runtime skills (`workspace/skills/`).

**Problems and fixes**
- Debugging protocol was missing from the original prompt; a placeholder was written, then replaced with the supplied 12-step protocol.
- `CLAUDE.md` named four specialists while the architecture has three; corrected to three.
- Docs-based facts for `deepagents` could not be checked against an installed package; unconfirmed items are marked VERIFY / *to verify* for Session 2.
- Docs note framework-internal files may be written under `workspace/`, which sits uneasily with the single-backend decision; deferred.

**Test results**
- No tests exist yet and pytest is not installed in the venv, so nothing was run: 0 passed, 0 failed, 0 skipped. The `live` auto-skip logic in `conftest.py` is therefore untested.

**Checkpoint status**
- No checkpoint was defined for this session. Against the Session 1 deliverables (structure, config, docs, no application code) all items are present; the test-based verification is outstanding.

## Session 2 - Minimal agent

**Built**
- Installed and pinned (`requirements.txt`): deepagents 0.7.34, langchain 1.4.9, langchain-core 1.7.6, langchain-openai 1.7.4, langgraph 1.2.20, langsmith 0.14.17, pydantic 2.14.3, python-dotenv 1.2.4, pytest 9.2.0. Tavily deferred until used. `pip check` clean.
- `app/config.py`: `Settings` (Pydantic, frozen, secrets as `SecretStr`) from env/.env: `MODEL`, `OPENAI_API_KEY`, optional Tavily and LangSmith keys, `LANGSMITH_PROJECT`, workspace path, `RECURSION_LIMIT` (default 100). `ConfigError` on missing key or bad `MODEL`/limit.
- `app/prompts.py`: `manager_prompt()` injects today's date and instructs planning with `write_todos`.
- `app/agent.py`: `build_agent(settings)` = `create_deep_agent(model, system_prompt, middleware=[TodoListMiddleware()], backend=FilesystemBackend(workspace/, virtual_mode=True))` then `.with_config(recursion_limit=...)`.
- `main.py`: minimal runner (`python main.py "request"`).
- Tests: `tests/test_config.py` (7 unit), `tests/test_agent.py` (3 unit, 1 integration, 1 e2e+live).

**Key decisions and why**
- Verified installed API: `model` accepts a `provider:model` string or a `BaseChatModel`; `openai:` strings use the Responses API by default (kept). `FilesystemBackend(root_dir, virtual_mode=True, max_file_size_mb)`; virtual mode rejects `..`, `~` and paths outside root. Docstring warns it is path semantics, not process sandboxing (accepted for the local POC).
- Planning is not in the default stack of 0.7.34; `TodoListMiddleware` is passed via `middleware=`. Library default recursion limit is 9999; we set 100 and make it a setting.
- LangSmith env names verified in installed langsmith: `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`. Tracing is enabled only when `LANGSMITH_TRACING=true` and a key is set; otherwise config sets `LANGSMITH_TRACING=false`, so the app runs either way.
- Secrets use `SecretStr` so repr/logs cannot leak them.

**Problems and fixes**
- `GenericFakeChatModel` lacks `bind_tools`: test subclass added.
- `conftest.py` skipped all live tests without Tavily; `@pytest.mark.live("KEY", ...)` now names required keys (default both).
- A shell command that inspected `.env` was blocked by the classifier; presence is now checked only via Python.
- Backend raises `ValueError` for traversal (the tool layer reports it as an error to the model); unit test expects the exception.
- `MODEL` initially lacked the `openai:` prefix; user corrected `.env`.

**Test results**
- Offline: 11 passed, 0 failed, 1 deselected. Full run including live/e2e: 12 passed, 0 failed, 0 skipped.
- Manual: `main.py` answered a simple request; multi-step request called `write_todos` and created `workspace/research/plan-test.md` (deleted after); `write_file` to `/../outside.md` returned "Path traversal not allowed" and no file was created.

**Checkpoint status**
- Passed. LangSmith: the user chose to keep tracing off for now (`LANGSMITH_TRACING` is not `true`); the API key is configured under `LANGSMITH_API_KEY` (it was first added under the legacy `LANGCHAIN_API_KEY` name and renamed). A traced run is therefore NOT verified; the on/off logic is unit-tested. To enable later: set `LANGSMITH_TRACING=true` in `.env`.
