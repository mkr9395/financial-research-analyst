# Architecture

Status: planned (Session 1). To be filled in as the agent is built.

- Main agent (Deep Agent): plans the research, delegates, synthesizes the report.
- Subagents: financial performance, AI business, competitive landscape, risks.
- Tools: Tavily web search.
- Workspace: `workspace/skills/` (committed), `workspace/memories/AGENTS.md` (committed), `workspace/research/` and `workspace/reports/` (git-ignored).
- Config: environment variables (`MODEL`, API keys) via `.env`.
