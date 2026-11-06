# Deep Financial Research Agent

Proof-of-concept financial research agent built with LangChain Deep Agents, OpenAI and Tavily. Given a request like "Analyze NVIDIA as an investment opportunity", it researches financials, AI business, competition and risks, then writes a structured analyst report.

**Status:** Session 1 — project foundation only; the agent is not implemented yet.

## Setup
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # then fill in your own keys
```

## Tests
```powershell
python -m pytest -m "not live"   # offline
python -m pytest -m live         # needs OPENAI_API_KEY and TAVILY_API_KEY
```

See `docs/architecture.md` and `docs/dev-log.md`.
