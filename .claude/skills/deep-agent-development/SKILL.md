---
name: deep-agent-development
description: Conventions for building the Deep Financial Research Agent with LangChain Deep Agents (deepagents) and OpenAI. Use when creating or modifying the agent, its subagents, tools, prompts, or workspace skills.
---

# Deep Agent development

## Rules
- Build on `deepagents` (`create_deep_agent`) with LangGraph underneath; do not hand-roll an agent loop.
- Model comes from the `MODEL` env var in `provider:model` form (e.g. `openai:<model-name>`). Never hardcode a model name or an API key.
- Search uses Tavily. Keep tools small, typed (pydantic), and documented with clear docstrings; the docstring is the tool description the model sees.
- Delegate focused work (financials, AI business, competitors, risks) to subagents; keep the main agent as planner and synthesizer.
- Runtime agent skills live in `workspace/skills/`, agent memory in `workspace/memories/AGENTS.md`. Research artifacts go to `workspace/research/`, final reports to `workspace/reports/` (both git-ignored).
- Code lives in `app/`. Check the installed `deepagents` version's docs/API before using an option; do not guess parameter names.

## Workflow
1. Read `docs/architecture.md` before changing structure.
2. Make the smallest change that works, then add or update tests (see the `testing` skill).
3. Record notable decisions in `docs/dev-log.md`.
4. Never read, print, or request secret values. Check keys only for presence.
