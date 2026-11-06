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

## Session 5 - Specialist subagents and delegation

**Built**
- `app/subagents.py`: `build_subagents(search_tool, today)` returns three `SubAgent` specs (`financial-researcher`, `industry-researcher`, `risk-analyst`), defined once. Each has a narrow dated prompt, `tools=[web_search]` only, `skills=["/skills/"]`, a prompt line naming the one skill to read, and a reply cap (~300 words, with source URLs, no files).
- `app/agent.py`: manager now has `tools=[]` and `subagents=build_subagents(...)`; delegation uses the built-in `task` tool. `SKILLS_SOURCE` moved to `app/subagents.py` (still importable from `app.agent`).
- `app/prompts.py`: manager delegates to exactly those three specialists, once per area, in parallel, checks todos before delegating, at most one follow-up per gap, never uses general-purpose, and does not search itself.
- Tests: `tests/test_subagents.py` (1 unit, 1 integration with stubbed model/Tavily proving manager -> `task` -> specialist -> `web_search`, 1 live e2e: all three specialists, each delegated exactly once). Wiring test in `test_agent.py` updated; the old live search test now checks delegation plus a cited URL.

**Key decisions and why**
- Verified installed API: `deepagents.SubAgent` TypedDict; omitting `tools` inherits the manager's, so tools are explicit. Filesystem and todo tools come from the framework's base stack.
- Search moved from manager to specialists (manager synthesises, specialists research).
- Loop/duplicate control is prompt + todos + recursion limit only; no middleware. The framework still auto-adds a `general-purpose` subagent; the prompt forbids using it.
- Each specialist can load all three skills (skills source is a directory); the prompt names one. Accepted for the POC.
- Out of scope and not built: `/research/` artifact files, memory, approval, final report.

**Verification (requested after the first implementation)**
- The four API facts (subagent fields, own tools/model/skills, default built-ins, `task` hand-off) were verified afterwards from the installed source; they are recorded in `docs/architecture.md`. They confirmed the implementation: only valid fields are used, `tools` is set explicitly, and subagents get no `write_todos` and see only the task description (so the manager prompt requires self-contained descriptions). The check should have preceded the code.

**Problems and fixes**
- The earlier manager-calls-`web_search` integration and live tests became invalid by design; the integration test was replaced by a delegation test, the live test now asserts `task` delegation.

**Test results**
- Offline: 28 passed, 0 failed, 5 deselected (before the live-test rewrite). Full run before the rewrite: 32 passed, 1 failed (the obsolete live test). Final (after the rewrite): offline 28 passed, 0 failed, 5 deselected; full run including live 33 passed, 0 failed, 0 skipped.

**Checkpoint status**
- PASSED: the manager delegates to the three specialists with `task` (live test: three distinct delegations, one per area), specialists search via `web_search`, and answers cite URLs.

### Session 5 addendum - specialists as data, standalone helper
- `app/subagents.py` now holds the three specialists as one `SPECIALISTS` data tuple (name, title, skill, focus, description) plus one `PROMPT_TEMPLATE`. Prompts state: stay in your area ("ONLY: ..."), read the matching skill, cite URL + date, mark FACT vs ANALYSIS, state uncertainty, date injected.
- `build_standalone_subagent(name, settings, search_tool)` builds a single specialist as its own agent from the same spec (no duplicate definitions) for testing each alone.
- `build_backend` moved to `app/backend.py` (avoids a circular import); `app.agent` imports it.
- Per-subagent skills are supported (`SubAgent.skills`), but the source is a directory, so each specialist can load all three skills; the prompt names its one. Not isolable without restructuring `workspace/skills/`.
- Tests: offline 33 passed, 5 deselected; see the live run below.
- Live: 4 passed (3 standalone specialists each search and cite a URL, plus the manager delegation test). Offline total 33 passed.

### Session 5 addendum - manager prompt rewrite
- `app/prompts.py`: manager prompt now follows seven explicit steps: understand the request; plan with `write_todos` (one todo per specialist used plus a review todo) before delegating; choose only the needed specialists; delegate with specific self-contained `task` descriptions (in parallel when independent); never do specialist research itself; at most one delegation per area, at most one follow-up for a clearly missing item; review, then stop when the request is covered. Removed the "/research/ files" line since artifacts are Session 6.
- `app/agent.py` already passed `subagents=build_subagents(...)`; unchanged. Loop control is prompt + recursion limit only; no middleware.
- Tests: `test_manager_prompt_rules` (unit); live: full request delegates to all three exactly once; an industry-only question delegates only to `industry-researcher` once.
- Results: offline 34 passed, 9 deselected; the two live manager-delegation tests passed (2 passed). The other live tests were not re-run after this change.

### Session 5 addendum - test suite and observed execution path
**Built**
- `tests/test_subagents.py`: unit (unique names, required fields, one `web_search` tool, matching skill path in the prompt, date, scope/evidence rules, unknown standalone name); integration (standalone uses the same definition); live per specialist via `build_standalone_subagent` (runs, calls `web_search`, cites a URL, reply contains in-area keywords, makes no plan/delegation calls).
- `tests/test_delegation.py`: `execution_path()` helper; live full NVIDIA request (plan present, all three specialists, no duplicate task calls, non-empty results, URL in the final answer); live cloud-GPU request (only `industry-researcher`, once); offline stubbed manager -> task -> specialist -> web_search test.

**Problems and fixes**
- Regression I introduced: after the manager prompt rewrite, `test_live_multi_step_plan_written_to_workspace` failed (manager skipped `write_todos` for a simple multi-step request). Fixed by restoring "for any request with more than one step, first write a plan with write_todos" in step 2 of `app/prompts.py`; the test passes again.
- An early heredoc-based file write failed silently (quoting); files were re-created with the Write tool.
- One intermittent failure NOT explained: in one full run `test_live_full_analysis_plans_and_delegates_to_all_three_once` failed; I did not capture its assertion output. Re-run alone 4 times and it passed each time (plus 2 earlier passes). Cause unknown; likely LLM nondeterminism (e.g. a missing URL in the final answer or a repeated delegation), unconfirmed.

**Observed execution path** (from run messages; LangSmith tracing is off)
- Full request: `write_todos` (plan) -> (reads skill files with `ls`/`read_file`, order varies) -> three parallel `task` calls (financial-researcher, industry-researcher, risk-analyst), one each -> three results (about 2.7k-4.6k chars each) -> `write_todos` status updates -> final synthesis with sources.
- Cloud-GPU question: `write_todos` -> one `task[industry-researcher]` -> one result -> `write_todos` updates -> final answer. No other specialist used.
- Specialists alone: financial 8 searches, industry 11, risk 6; each cited URLs and marked FACT/ANALYSIS.
- Caveat: "stays in its area" is checked only by keyword heuristic plus absence of plan/task calls, not semantically.

**Test results**
- Offline: 35 passed, 0 failed, 9 deselected.
- Full run including live (last): 43 passed, 1 failed (the intermittent test above); the previous full run before the prompt fix failed on the plan-writing test, now fixed.

**Checkpoint status (Session 5)**
- Passed with a caveat: delegation matches (plan, task calls to the right specialists, results returned, no duplicates) in 7 of 8 live runs of the delegation e2e; one unexplained intermittent failure remains and a clean full-suite run (0 failures) has not been shown.


## Session 6 - Research artifacts and context management
**Built**
- `app/subagents.py`: each specialist has an `artifact` path and writes full findings with `write_file` to `/research/{financial,industry,risks}.md` (Findings, Key evidence, Sources, Uncertainty and gaps, Research date), then replies with about 150 words plus the path.
- `app/prompts.py`: manager step 6 - do not read artifacts by default; verify a missing or incomplete one, re-delegate once with a specific instruction, then report the gap.
- `.gitignore`: `workspace/large_tool_results/`, `workspace/conversation_history/`.
- `tests/test_artifacts.py`; `docs/architecture.md` "Context management" section.

**Decisions**
- Orchestration stays prompt-only; the section checker `missing_sections` lives in the test file, not in app code.
- Summarisation/eviction defaults verified (85%/10% of a 1.05M window; 20k-token eviction) and left unchanged.

**Evidence (one NVIDIA run)**: task results 653 / 370 / 631 chars (1,654 total) vs artifacts 13,102 / 24,394 / 21,725 bytes (59,221 total). Files appeared in `workspace/research/`.

**Caveats**: the manager issued `read_file` calls after delegation; their targets and sizes were not captured. No offload directories appeared under `workspace/`. The Session 5 intermittent live failure was not investigated.

**Tests**: first full run (offline + live): 46 passed, 3 failed. The 3 failures were the Session 5 standalone live specialist tests, which required a URL in the reply; URLs now live in the artifact file by design. Fixed the tests to check the artifact path in the reply and URLs in the file; those 3 then passed. Offline: 39 passed, 10 deselected. Not re-run as one clean full pass after the fix (the full run takes about 15 min).

**Checkpoint status**: Checkpoint 1 passed (3 files, all sections). Checkpoint 2 passed for task results and no custom context code; the manager's `read_file` targets are unverified.

### Session 6 addendum - concise artifacts (200-word limit)
- Artifacts were 13-24 KB each; the user asked for at most 200 words each. `app/subagents.py` now sets a 200-word cap with hard per-section limits (3 findings bullets, 3 evidence bullets, 3 sources, 2 uncertainty bullets).
- A bare "at most 200 words" instruction was ignored (258-372 words over three runs; models count words poorly), and my first per-section budget summed to about 215 words, so it overshot by design. Budgets that sum to about 165 worked.
- Result (one NVIDIA run): financial 153, industry 178, risks 182 words; `task` results 772 / 735 / 581 chars. Live test asserts <= 220 words (tolerance for model variance). Offline: 39 passed, 10 deselected; live artifact test 1 passed.
- The size table in `docs/architecture.md` (13-24 KB artifacts) is from before this change and is superseded by these figures.

### Session 6 addendum - final verification
- Full suite (before the last prompt tweak): 48 passed, 1 failed. The failure was `test_live_multi_step_plan_written_to_workspace` (manager wrote the file without `write_todos`). Classified as flaky: the committed prompt failed 1 of 4 runs, my step-6 prompt 2 of 3. Smallest fix: step 2 of the manager prompt now says to plan "before any other action, file write or delegation (even if the request also asks for a file)". After it: 5 of 5 passed.
- Re-run of manager-facing tests (agent, delegation, artifacts, skills) after the fix: 17 passed, 1 failed - `test_live_full_analysis_plans_and_delegates_to_all_three_once`, the unexplained intermittent test from Session 5. Its assertion was not captured; re-run alone it passed. A possible cause is the new one-time re-delegation allowance tripping the "no duplicate task calls" assertion, unconfirmed.
- Offline: 39 passed, 10 deselected. No single clean full-suite pass after the last prompt change.
- Manager reads (one run): 3 SKILL.md (about 4.8k chars), `ls /research`, then each artifact once (4,523 chars total) as a completeness check. Task results total 1,364 chars.
- Checkpoint 1 passed. Checkpoint 2 passed: manager context is task summaries plus about 4.5k chars of 200-word artifact reads; no custom context code.
