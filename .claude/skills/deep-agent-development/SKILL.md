---
name: deep-agent-development
description: How to build the Deep Financial Research Agent with LangChain Deep Agents (deepagents) and OpenAI. Covers planning with write_todos, the filesystem backend, context management, subagent delegation with task, runtime skills, memory, human-in-the-loop with interrupt_on and a checkpointer, custom tools, structured output, and when to use built-ins instead of custom orchestration. Use when creating or changing the agent, subagents, tools, prompts, or workspace skills.
---

# Deep Agent development

Facts below were checked against the official docs (docs.langchain.com/oss/python/deepagents) while writing this skill. The `deepagents` package may not be installed yet, and signatures change between versions. Per CLAUDE.md: before using anything, inspect the installed package (`pip show deepagents`, `python -c "import inspect, deepagents; print(inspect.signature(deepagents.create_deep_agent))"`). Items marked **VERIFY** were not confirmed from the docs.

## Use built-ins first
Deep Agents already provide planning, a virtual filesystem, subagent delegation, skills, memory and human-in-the-loop. Use them. Do not write custom LangGraph graphs, custom orchestration, or custom middleware for loop control (a fixed project decision). Steer behaviour with the manager system prompt and a recursion limit. Only add custom code for things the framework lacks: domain tools, report rendering, the CLI/run loop.

## Planning: `write_todos`
- Built-in tool from `TodoListMiddleware`; statuses are `pending`, `in_progress`, `completed`.
- Docs say planning is opt-in as of v0.7. **VERIFY** how to enable it in the installed version (e.g. `middleware=[TodoListMiddleware()]` or a default).
- The manager prompt should tell the agent to plan first, update todos as work completes, and not re-delegate work already marked complete (this is our duplicate-delegation control).

## Filesystem backend
- `from deepagents.backends import FilesystemBackend`; constructor `FilesystemBackend(root_dir=..., virtual_mode=True)`.
- **Always `virtual_mode=True`.** The docs state that with the default `virtual_mode=False` the backend gives "no security even with `root_dir` set". With `True`, `..`, `~` and absolute paths outside `root_dir` are blocked.
- Use an absolute `root_dir` pointing at `workspace/` (resolve from the project root, never the CWD).
- Agent-visible paths: `/skills/`, `/research/`, `/reports/`, `/memories/AGENTS.md`.
- Built-in file tools: `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep` (`delete` in >=0.7). `execute` exists only with sandbox/shell backends: never use `LocalShellBackend`, it can reach any path.
- Docs note that internal files (such as offloaded tool results under `/large_tool_results/`) get written under `root_dir`. Expect extra files in `workspace/`; keep them out of git. Our decision is a single FilesystemBackend, so do not introduce a `CompositeBackend` without asking.

## Context management
- Keep big content in files, not in messages: specialists write full findings to `/research/<area>.md` and return a short summary plus the path.
- The manager reads only the files it needs, and tells specialists a length cap for their returned summary.
- Subagents run isolated by default, so the manager's history does not bloat theirs.
- Prefer targeted `grep`/`read_file` over reading whole files repeatedly.

## Subagent delegation with `task`
- Define each specialist once in `app/subagents.py` as a dict and pass `subagents=[...]` to `create_deep_agent`.
- Fields: `name` (required), `description` (required; the manager uses it to choose), `system_prompt` (required in default isolated mode; not inherited), optional `tools`, `model`, `skills`, `permissions`, `interrupt_on`, `response_format`.
- `tools`, if set, replaces inherited tools entirely: keep minimal (search plus what is needed). **VERIFY** the specialist can still write to `/research/` when `tools` is overridden (filesystem tools come from middleware; confirm in the installed version).
- Custom subagents do not inherit the main agent's skills: pass `skills` explicitly if needed.
- The manager delegates by calling `task` with `subagent_type=<name>`; it receives only the subagent's final message.
- Specialist prompts must specify: steps, the output file `/research/<area>.md`, source citation, and a short return format.

## Runtime skills (`workspace/skills/`)
- Not the same as `.claude/skills/` (Claude Code dev skills). Never mix them.
- Format: `workspace/skills/<skill-name>/SKILL.md` with frontmatter `name` (lowercase letters, numbers, hyphens, 1-64 chars, must equal the directory name) and `description` (up to 1024 chars). Keep bodies under ~500 lines.
- Pass `skills=["/skills/"]`: each entry is a **source directory containing skill directories**. Pointing it at a single skill directory loads nothing and raises no error.
- Progressive disclosure: only name/description are in the prompt; the body is read when relevant.
- With `FilesystemBackend`, skills already on disk under `root_dir` load without uploading.

## Memory
- `memory=["/memories/AGENTS.md"]` loads the file at startup. No database.
- The file must exist in the backend before the agent is created. **VERIFY** how the installed version resolves memory paths and whether the agent can update it.
- Keep it short, stable guidance (role, citation rules), not research data.

## Human-in-the-loop (`interrupt_on` + checkpointer)
- Dedicated tool `submit_draft_assessment`; `interrupt_on={"submit_draft_assessment": True}` (or `{"allowed_decisions": [...]}`).
- A checkpointer is required (e.g. `MemorySaver` from `langgraph.checkpoint.memory`), plus `config={"configurable": {"thread_id": ...}}`. Resume with the same config.
- Detect with `result.get("__interrupt__")`; requests are in `result["__interrupt__"][0].value["action_requests"]`.
- Resume with `Command(resume={"decisions": [...]})` (`from langgraph.types import Command`), one decision per request, same order. Types: `approve`, `edit` (supply `edited_action` with `name` and `args`), `reject` (optional `message`), `respond`. Use `reject`, not `respond`, to deny.
- Never use `input()` as the approval gate.

## Custom tools
- Plain typed functions or LangChain tools. The docstring and type hints are what the model sees: write them for the model.
- Validate inputs, return concise strings or structured data, and raise clear errors rather than swallowing them.
- Tools: Tavily search (via `langchain-tavily`, **VERIFY** class name and parameters) and `submit_draft_assessment`.

## Structured output
- `response_format=ResearchReport` (a Pydantic model) on `create_deep_agent`; accepted types include a Pydantic class.
- **VERIFY** where the validated object appears in the result (commonly `result["structured_response"]`).
- Python renders `workspace/reports/final_report.md` from the validated object; the model does not write the final Markdown.

## Run settings
- Date: inject today's date into every system prompt (manager and subagents).
- Recursion limit: pass `recursion_limit` in the invoke `config` (LangGraph config key). **VERIFY** the installed default and a sensible value for this POC.
- Model: `create_deep_agent(model=os.environ["MODEL"], ...)` in `provider:model` form; never hardcode.

## Workflow
1. Read `docs/architecture.md`.
2. Verify the installed API, then make the smallest change that works.
3. Add or update tests (see the `testing` skill).
4. Record decisions in `docs/dev-log.md`.
5. Never read, print, or request secret values; check keys only for presence.
