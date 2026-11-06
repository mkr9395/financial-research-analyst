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

## Session 3 - Web search tool

**Built**
- Installed `langchain-tavily` 0.2.18 (the Tavily integration the search tool wraps); pinned in `requirements.txt`; `pip check` clean.
- `app/tools.py`: `build_web_search_tool(settings, search=None)` returns a `web_search(query, topic, time_range)` tool. Bounded to 5 results, snippets capped at 1200 chars, output labelled as untrusted, docstring written for the model. `ConfigError` if `TAVILY_API_KEY` is missing.
- Wired into `build_agent()` via `tools=`; manager prompt tells it to use `web_search` and cite URLs.
- `tests/test_tools.py`: 6 unit, 1 integration (agent -> ToolNode -> stubbed Tavily), 1 live.

**Key decisions and why**
- Verified installed API: `TavilySearch._run` raises `ToolException` on no results but returns `{"error": exc}` for API/network failures. The tool converts both into explicit `Search error: ...` strings so the model sees the failure and can rephrase; nothing is silently swallowed or empty.
- `max_results`, depth and other instantiation-only params are fixed in code, not exposed to the model (Tavily forbids them at invoke time anyway).
- The tool is on the manager for now (nothing else exists to use it); it moves to specialists in Session 4.

**Problems and fixes**
- Existing agent test fixture lacked a Tavily key, so `build_agent` raised `ConfigError`; fixture updated.
- Live search returned 401 (missing/invalid Tavily key): the error was surfaced to the model correctly, which declined to quote figures. A `.env` probe was blocked by the permission classifier and not retried.

**Test results**
- Offline: 18 passed, 0 failed, 2 deselected. Full run: 18 passed, 2 failed, 0 skipped. Failures: the Tavily live test (401) and `test_live_multi_step_plan_written_to_workspace` on one run; the latter passed when re-run alone (1 passed), so it is LLM-nondeterministic.

**Checkpoint status**
- NOT fully passed: the offline checkpoint passes, but a live search returning real results is unverified because the Tavily key is rejected (401). Needs a valid `TAVILY_API_KEY` in `.env`.

### Session 3 addendum - search tool hardening
- `Settings.tavily_api_key` is now required: `load_settings()` raises `ConfigError` at startup if it is missing (previously only when the tool was built).
- New settings `SEARCH_MAX_RESULTS` (default 5) and `SEARCH_SNIPPET_CHARS` (default 1000), validated as positive integers via a shared `_positive_int` helper (also used for `RECURSION_LIMIT`).
- `app/tools.py`: typed `SearchResult` model and `normalise_results()`; explicit `No results found for '<query>'.`; a broad `except Exception` in the tool converts any transport failure (timeout, connection) into a `Search error (<Type>)` message for the model. This is deliberate and reported, never silent.
- `.env.example` was deleted by the user; docs that mention it are now stale.
- Tests added: missing-key config test in `test_tools.py`; the live search test is now marked `integration` + `live`; new `e2e` + `live` test asks the agent for NVIDIA's latest quarterly revenue and asserts `web_search` was called, returned `URL: http`, and the final answer cites a URL.

**Switch to the standalone Tavily SDK (user decision)**
- Replaced `langchain-tavily` with `tavily-python` 0.8.5 (Tavily's own SDK; the user wanted it instead of the LangChain wrapper). Uninstalled `langchain-tavily`; `requirements.txt` pins `tavily-python==0.8.5`; `pip check` clean.
- Verified API: `from tavily import TavilyClient`; `TavilyClient(api_key=...)`; `search(query, topic, time_range, max_results, timeout, ...) -> dict` with `results[{title,url,content,score,published_date?}]`. Errors are raised as typed exceptions (`InvalidAPIKeyError`, `ForbiddenError`, `BadRequestError`, `UsageLimitExceededError`, `tavily.errors.TimeoutError`) plus `requests` exceptions.
- Because errors are real exceptions, the broad `except Exception` and the `{"error": exc}` dict handling were removed; the tool catches only the known Tavily/network exceptions (`TAVILY_ERRORS`), so a genuine bug still surfaces. Added a 30 s request timeout.
- Tests: stub client replaces the stub LangChain tool; parametrised known-error test; test that an unexpected `RuntimeError` is not swallowed.
- The earlier persistent 401 came through the `langchain-tavily` path; with the SDK the live tests pass. Root cause not isolated (the key was not inspected, per security rules).

**Final test results (Session 3)**
- Offline: 24 passed, 0 failed, 3 deselected. Full run including live: 27 passed, 0 failed, 0 skipped.
- Manual live searches: finance and news queries returned relevant NVIDIA results with URLs; news results carry `published_date`. Caveat: the top finance hit was an older earnings preview, so ranking does not guarantee the latest quarter; the research prompts must ask for dates and verify recency.

**Checkpoint status (Session 3)**
- PASSED: search returns real, sourced results; the agent calls `web_search` and cites a URL (live e2e test).

## Session 4 - Runtime skills

**Built**
- `workspace/skills/` (agent path `/skills/`, committed) with three runtime skills: `financial-analysis` (revenue, margins, earnings, cash flow, trends; every figure states its fiscal period, source and date; facts vs analysis), `investment-research` (thesis, competitive position, strengths/weaknesses, valuation, uncertainty), `risk-analysis` (financial, regulatory, competitive, technology, business-model risks; likelihood and impact ratings; uncertainty).
- `app/agent.py`: `SKILLS_SOURCE = "/skills/"` passed as `skills=[SKILLS_SOURCE]`; manager prompt has one line telling it to read a matching skill (no skill content in the prompt).
- `tests/test_skills.py`: 2 unit (real skills load without errors and names match; `skills` wiring), 1 integration (names and descriptions reach the model prompt, SKILL.md bodies do not: progressive disclosure), 1 e2e+live (agent reads `/skills/risk-analysis/SKILL.md`).

**Key decisions and why**
- Verified installed API first (second time, after being asked): deepagents 0.7.34; `skills: list[str]` of source directories relative to the backend root; `SKILL.md` frontmatter `name` (= directory name) and `description` (<=1024 chars) required.
- A first set (`source-citation`, `financial-analysis`, `analyst-report-structure`) was replaced when the spec named different skills. Citation rules now live in `financial-analysis`; report-structure guidance has no skill and will be needed with `ResearchReport` (Session 6/7).
- Skills attach to the manager only for now. Session 5 gives each specialist its one skill via `SubAgent.skills` (supported; forks cannot).

**Problems and fixes**
- Code was first written before the API checks were done; checks were run afterwards and confirmed it.
- The unit test uses the private `_list_skills_with_errors` helper (load problems are otherwise only logged); may need updating on a deepagents upgrade.

**Test results**
- Offline: 27 passed, 0 failed, 4 deselected. Full run including live: 31 passed, 0 failed, 0 skipped.

**Checkpoint status**
- PASSED: skills load from `/skills/`, only names/descriptions are in the prompt, and the live agent read the matching SKILL.md.
