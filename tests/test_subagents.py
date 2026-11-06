"""Tests for the specialist subagent definitions and each specialist run on its own."""
from datetime import date

import pytest
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from app import tools as tools_module
from app.config import Settings, load_settings
from app.subagents import build_standalone_subagent, build_subagents
from tests.test_agent import FakeToolModel
from tests.test_tools import StubClient

NAMES = ["financial-researcher", "industry-researcher", "risk-analyst"]
SKILL_FOR = {
    "financial-researcher": "financial-analysis",
    "industry-researcher": "investment-research",
    "risk-analyst": "risk-analysis",
}


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        model="openai:placeholder",
        openai_api_key=SecretStr("sk-test"),
        tavily_api_key=SecretStr("tvly-test"),
        workspace_dir=tmp_path,
    )


@pytest.fixture
def search_tool(settings):
    return tools_module.build_web_search_tool(settings, client=StubClient(response={"results": []}))


@pytest.mark.unit
def test_names_are_unique_and_complete(search_tool):
    names = [s["name"] for s in build_subagents(search_tool)]
    assert names == NAMES and len(set(names)) == 3


@pytest.mark.unit
def test_definitions_have_required_fields_tool_and_skill(search_tool):
    for s in build_subagents(search_tool, date(2026, 11, 6)):
        assert s["description"].strip() and s["system_prompt"].strip()
        assert [t.name for t in s["tools"]] == ["web_search"]
        assert s["skills"] == ["/skills/"]
        assert f"/skills/{SKILL_FOR[s['name']]}/SKILL.md" in s["system_prompt"]
        assert "2026-11-06" in s["system_prompt"]


@pytest.mark.unit
def test_prompts_state_scope_and_evidence_rules(search_tool):
    for s in build_subagents(search_tool):
        for phrase in ("Stay within your area", "source URL", "FACT", "ANALYSIS", "uncertainty"):
            assert phrase in s["system_prompt"], (s["name"], phrase)


@pytest.mark.unit
def test_standalone_unknown_name_rejected(settings):
    with pytest.raises(ValueError, match="Unknown subagent"):
        build_standalone_subagent("nope", settings, search_tool=None)


@pytest.mark.integration
@pytest.mark.parametrize("name", NAMES)
def test_standalone_subagent_uses_same_definition(settings, monkeypatch, name):
    import app.subagents as sub

    stub = StubClient(response={"results": [{"title": "T", "url": "https://e.com", "content": "c"}]})
    monkeypatch.setattr(tools_module, "TavilyClient", lambda **kw: stub)
    tool = tools_module.build_web_search_tool(settings)
    captured = {}
    real = sub.create_deep_agent
    fake = FakeToolModel(messages=iter([
        AIMessage(content="", tool_calls=[{"name": "web_search", "args": {"query": "q"}, "id": "1"}]),
        AIMessage(content="ok https://e.com"),
    ]))

    def spy(**kw):
        captured.update(kw)
        return real(**{**kw, "model": fake})

    monkeypatch.setattr(sub, "create_deep_agent", spy)
    agent = build_standalone_subagent(name, settings, tool)
    spec = next(s for s in build_subagents(tool) if s["name"] == name)
    assert captured["system_prompt"] == spec["system_prompt"]
    out = agent.invoke({"messages": [{"role": "user", "content": "go"}]})
    assert stub.calls[0]["query"] == "q" and "https://e.com" in out["messages"][-1].text


# One representative question per specialist, with words a correct in-area answer contains.
QUESTIONS = {
    "financial-researcher": (
        "What were NVIDIA's most recent quarterly revenue, gross margin and operating cash flow?",
        ("revenue", "margin", "cash flow"),
    ),
    "industry-researcher": (
        "Who are NVIDIA's main competitors in AI accelerators and what technology trends matter?",
        ("amd", "competit", "trend"),
    ),
    "risk-analyst": (
        "What are the main regulatory and competitive risks facing NVIDIA?",
        ("risk", "regulat", "export"),
    ),
}


@pytest.mark.e2e
@pytest.mark.live("OPENAI_API_KEY", "MODEL", "TAVILY_API_KEY")
@pytest.mark.parametrize("name", NAMES)
def test_live_standalone_specialist_runs_searches_and_stays_in_area(name):
    question, terms = QUESTIONS[name]
    settings = load_settings()
    agent = build_standalone_subagent(name, settings, tools_module.build_web_search_tool(settings))
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    msgs = result["messages"]
    calls = [tc for m in msgs if m.type == "ai" for tc in m.tool_calls]
    searches = [c for c in calls if c["name"] == "web_search"]
    reply = msgs[-1].text
    print(f"\n[{name}] searches={[c['args'].get('query') for c in searches]}")
    print(f"[{name}] reply={reply[:300]!r}")
    assert searches, "specialist never called web_search"
    assert "http" in reply, "no source URL in the reply"
    assert any(t in reply.lower() for t in terms), f"reply does not address its area ({terms})"
    assert not {c["name"] for c in calls} & {"write_todos", "task"}, "specialist planned or delegated"
