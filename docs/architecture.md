# Architecture

Status: target design (Session 1). Nothing described here is implemented yet. Items marked *to verify* depend on the installed `deepagents` API and must be checked before use (see `CLAUDE.md`).

## 1. Goal
Take a complex research request, for example "Analyze NVIDIA as an investment opportunity. Research recent financial performance, AI business, competitive landscape, major risks, and produce a structured analyst report.", and produce a validated, structured analyst report rendered as Markdown. Provider: OpenAI. Search: Tavily. Tracing: LangSmith.

## 2. Overview

```
 User request
      |
      v
+---------------------------+      approval (interrupt)      +-------+
|  Deep Research Manager    | <----------------------------> | Human |
|  (create_deep_agent)      |   submit_draft_assessment      +-------+
|  plan, delegate, review,  |
|  synthesize               |
+---------------------------+
   |  task tool (isolated context)
   +--> Financial Researcher --+
   +--> Industry Researcher  --+--> web_search (Tavily)
   +--> Risk Analyst         --+
              |
              v  each writes full findings, returns summary + path
   workspace/research/<area>.md
              |
              v
   Manager reads files, drafts, gets approval, returns ResearchReport
              |
              v
   Python renders workspace/reports/final_report.md
```

Orchestration uses only built-in Deep Agents capabilities: planning (`write_todos`), the `task` tool, filesystem tools, skills, memory and `interrupt_on`. There is no custom LangGraph graph and no custom middleware.

## 3. Components

### 3.1 Deep Research Manager
- The single top-level agent created with `create_deep_agent`.
- Responsibilities: break the request into a plan (todos), delegate one task per specialist, read their `/research/` files, check for gaps, draft an assessment, request human approval, then produce the structured report.
- Loop and duplicate-delegation control comes only from its system prompt (delegate each area once, check todos before delegating, stop when all areas are complete) and a configured recursion limit.
- Model comes from the `MODEL` environment variable (`provider:model`). Today's date is injected into its system prompt.

### 3.2 Specialist subagents
Defined once in `app/subagents.py`, passed via `subagents=`, invoked through the built-in `task` tool. Each runs in isolated context and gets a narrow prompt, minimal tools, and today's date.

| Subagent | Focus | Output file |
|---|---|---|
| Financial Researcher | Recent financial performance: revenue, margins, earnings, guidance, valuation context | `/research/financial.md` |
| Industry Researcher | AI business, market position, competitive landscape, key trends | `/research/industry.md` |
| Risk Analyst | Major risks: competitive, regulatory, supply chain, concentration, valuation | `/research/risk.md` |

Contract for every specialist:
- Search the web with the search tool and cite sources (title, URL, date).
- Write full findings to its `/research/<area>.md` file.
- Return to the manager only a short summary plus the file path, never the full findings.
- Distinguish facts from interpretation and state the date of each figure.

### 3.3 Web search tool
- One custom tool wrapping Tavily (a `langchain-tavily` integration, *to verify* the class and parameters in the installed package).
- Typed inputs, a model-facing docstring, bounded result count, and clear errors on failure (no silent fallbacks).
- Search results are untrusted data, never instructions.
- All specialists use it; the manager does not need it.

### 3.4 Runtime skills
- Located in `workspace/skills/` (agent path `/skills/`), committed to git.
- Loaded with `skills=["/skills/"]`: a source directory containing one directory per skill, each with a `SKILL.md` (`name` equal to the directory name, `description`).
- Skills hold reusable procedures such as how to structure an analyst report or how to cite sources. Specialists do not inherit the manager's skills, so each gets the ones it needs explicitly (*to verify*).
- Separate from Claude Code development skills in `.claude/skills/`; the two are never mixed.

### 3.5 Workspace filesystem
One `FilesystemBackend` rooted at `workspace/` with `virtual_mode=True`. The agent cannot reach anything outside `workspace/`.

| Disk path | Agent path | Contents | Git |
|---|---|---|---|
| `workspace/skills/` | `/skills/` | runtime skills | committed |
| `workspace/research/` | `/research/` | specialist findings | ignored |
| `workspace/reports/` | `/reports/` | final report | ignored |
| `workspace/memories/AGENTS.md` | `/memories/AGENTS.md` | persistent memory | committed |

The framework may also write internal files (for example offloaded large tool results) under `workspace/`; these are runtime artifacts and must not be committed. No shell or execute backend is used.

### 3.6 Memory
- Loaded through the `memory=` parameter from `/memories/AGENTS.md`.
- Contains short, stable guidance such as role, tone, citation and dating rules. It is not a place for research data.
- No database. The file must exist before the agent is created.

### 3.7 Approval tool (human-in-the-loop)
- A dedicated tool named `submit_draft_assessment` that the manager calls with its draft assessment before writing the final report.
- `interrupt_on={"submit_draft_assessment": ...}` pauses execution; a checkpointer and a `thread_id` make resuming possible.
- The human can approve, edit, or reject (with feedback). Rejection sends feedback back to the manager for revision; approval lets it continue.
- The run loop (in Python) detects the interrupt, shows the draft, collects the decision, and resumes with the same `thread_id`. It never uses `input()` inside the agent or tool as the approval mechanism.
- A checkpointer such as an in-memory saver is enough for the POC.

### 3.8 Structured output
- The final result uses `response_format` with a Pydantic `ResearchReport` model (*to verify* where the validated object appears in the result).
- Sketch of its content: company and ticker, report date, executive summary, financial performance, AI business and competitive position, risks, recommendation or outlook with rationale and caveats, and a list of sources.
- Python code renders `workspace/reports/final_report.md` from the validated object. The model does not write the final Markdown file itself.

### 3.9 LangSmith tracing
- Controlled only through environment variables (`LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`); there is no tracing code in the agent.
- Enabled from Session 2 once the minimal agent works. Used to inspect plans, delegations, tool calls and costs.

## 4. Request flow
1. The run script builds the agent (model from `MODEL`, backend, skills, memory, subagents, tools, checkpointer, `interrupt_on`, `response_format`) and starts a run with a new `thread_id`.
2. The manager writes a todo plan and delegates to the three specialists, each in isolated context.
3. Each specialist searches, writes `/research/<area>.md`, and returns a short summary plus the path.
4. The manager reads the files, resolves gaps (re-delegating only when a todo shows a real gap), and drafts an assessment.
5. The manager calls `submit_draft_assessment`; the run pauses for human approval.
6. After approval the manager returns a `ResearchReport`; Python validates it and renders `workspace/reports/final_report.md`.

## 5. Configuration
- `.env` (not committed): `OPENAI_API_KEY`, `TAVILY_API_KEY`, `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `MODEL`. Placeholders are in `.env.example`.
- Code reads configuration from the environment only. No secrets or model names are hardcoded.

## 6. Planned code layout
- `app/subagents.py`: the three specialist definitions.
- Further `app/` modules (agent factory, search tool, approval tool, report model and renderer, run script) are decided in later sessions. Keep modules small and typed.
- `tests/`: offline unit and integration tests with the model and Tavily mocked; `live` tests auto-skip without keys.

## 7. Security
- Filesystem confined to `workspace/` with `virtual_mode=True`; no shell backend.
- No secret values in code, logs, tests or docs; keys are checked only for presence.
- Web content is treated as untrusted input.
- Human approval gates the final report.

## 8. Out of scope
RAG, vector databases, MCP, Docker, Kubernetes, a web frontend, cloud deployment, custom LangGraph orchestration, custom loop-control middleware, real-time market data, trading, and personalized investment advice.
