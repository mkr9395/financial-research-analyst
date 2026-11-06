# Deep Financial Research Agent

A 2-day proof-of-concept: a LangChain Deep Agents financial research agent that takes a complex request (e.g. "Analyze NVIDIA as an investment opportunity...") and produces a structured analyst report. Model provider: OpenAI. Search: Tavily. Tracing: LangSmith.

## Layout
- `app/` application code
- `tests/` pytest suite (markers: unit, integration, e2e, live)
- `workspace/skills/` runtime Deep Agents skills (committed)
- `workspace/memories/AGENTS.md` agent memory (committed)
- `workspace/research/`, `workspace/reports/` agent outputs (git-ignored)
- `docs/` architecture, dev log, exported Claude Code sessions

## Rules
- Python 3.11+, use the project `.venv`.
- NEVER read, print, or ask for secret values. `.env` is denied in `.claude/settings.json`. Check whether a key is set, never its value. Placeholders live in `.env.example`.
- Model is configured via `MODEL` (`provider:model`); do not hardcode it.
- Session scope matters: do only what the current session's prompt asks.
- Record decisions in `docs/dev-log.md`; keep `docs/architecture.md` current.

## Commands
- Activate venv (PowerShell): `.\.venv\Scripts\Activate.ps1`
- Tests (offline): `python -m pytest -m "not live"`
