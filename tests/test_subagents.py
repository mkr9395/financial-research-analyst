"""Tests for the specialist subagents and manager delegation via the task tool (model and Tavily stubbed)."""
from datetime import date

import pytest
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from app import agent as agent_module
from app import tools as tools_module
from app.config import Settings, load_settings
from app.subagents import build_standalone_subagent, build_subagents
from tests.test_agent import FakeToolModel
from tests.test_tools import StubClient

NAMES = ["financial-researcher", "industry-researcher", "risk-analyst"]


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        model="openai:placeholder",
        openai_api_key=SecretStr("sk-test"),
        tavily_api_key=SecretStr("tvly-test"),
        workspace_dir=tmp_path,
    )


@pytest.mark.unit
def test_specialists_are_narrow_and_dated(settings):
    tool = tools_module.build_web_search_tool(settings, client=StubClient(response={"results": []}))
    specs = build_subagents(tool, date(2026, 11, 6))
    assert [s["name"] for s in specs] == NAMES
    for s in specs:
        assert [t.name for t in s["tools"]] == ["web_search"]
        assert "2026-11-06" in s["system_prompt"]
        assert s["description"] and s["skills"] == ["/skills/"]
    skills = {s["name"]: s["system_prompt"] for s in specs}
    assert "/skills/financial-analysis/SKILL.md" in skills["financial-researcher"]
    assert "/skills/investment-research/SKILL.md" in skills["industry-researcher"]
    assert "/skills/risk-analysis/SKILL.md" in skills["risk-analyst"]


@pytest.mark.unit
def test_prompts_state_scope_and_evidence_rules(settings):
    tool = tools_module.build_web_search_tool(settings, client=StubClient(response={"results": []}))
    for s in build_subagents(tool):
        p = s["system_prompt"]
        for phrase in ("Stay within your area", "source URL", "FACT", "ANALYSIS", "uncertainty"):
            assert phrase in p, (s["name"], phrase)


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


@pytest.mark.unit
def test_standalone_unknown_name_rejected(settings):
    with pytest.raises(ValueError, match="Unknown subagent"):
        build_standalone_subagent("nope", settings, search_tool=None)


@pytest.mark.integration
def test_manager_delegates_to_specialist_which_searches(settings, monkeypatch):
    stub = StubClient(response={"results": [{"title": "T", "url": "https://e.com", "content": "c"}]})
    monkeypatch.setattr(tools_module, "TavilyClient", lambda **kw: stub)
    task = AIMessage(content="", tool_calls=[{
        "name": "task",
        "args": {"description": "Research NVDA financials", "subagent_type": "financial-researcher"},
        "id": "t1",
    }])
    search = AIMessage(content="", tool_calls=[{"name": "web_search", "args": {"query": "nvda"}, "id": "s1"}])
    fake = FakeToolModel(messages=iter([
        task, search, AIMessage(content="Revenue up. https://e.com"), AIMessage(content="final")
    ]))
    real = agent_module.create_deep_agent
    monkeypatch.setattr(agent_module, "create_deep_agent", lambda **kw: real(**{**kw, "model": fake}))
    result = agent_module.build_agent(settings).invoke({"messages": [{"role": "user", "content": "go"}]})
    task_msgs = [m for m in result["messages"] if m.type == "tool" and m.name == "task"]
    assert "https://e.com" in task_msgs[0].content
    assert stub.calls[0]["query"] == "nvda"
    assert result["messages"][-1].text == "final"


@pytest.mark.e2e
@pytest.mark.live("OPENAI_API_KEY", "MODEL", "TAVILY_API_KEY")
def test_live_manager_delegates_to_all_specialists():
    agent = agent_module.build_agent(load_settings())
    result = agent.invoke({"messages": [{"role": "user", "content": (
        "Analyze NVIDIA as an investment opportunity: recent financial performance, "
        "AI business and competition, and major risks. Keep it brief."
    )}]})
    calls = [tc for m in result["messages"] if m.type == "ai" for tc in m.tool_calls if tc["name"] == "task"]
    assert {c["args"]["subagent_type"] for c in calls} == set(NAMES)
    assert len(calls) == 3, "each area should be delegated exactly once"


@pytest.mark.e2e
@pytest.mark.live("OPENAI_API_KEY", "MODEL", "TAVILY_API_KEY")
@pytest.mark.parametrize("name", NAMES)
def test_live_standalone_specialist_searches_and_cites(name):
    settings = load_settings()
    agent = build_standalone_subagent(name, settings, tools_module.build_web_search_tool(settings))
    result = agent.invoke({"messages": [{"role": "user", "content": "Analyze NVIDIA in your area. Keep it brief."}]})
    searched = [tc for m in result["messages"] if m.type == "ai" for tc in m.tool_calls if tc["name"] == "web_search"]
    assert searched, "specialist never searched"
    assert "http" in result["messages"][-1].text, "no source URL in the reply"


@pytest.mark.e2e
@pytest.mark.live("OPENAI_API_KEY", "MODEL", "TAVILY_API_KEY")
def test_live_industry_only_question_uses_only_industry_researcher():
    result = agent_module.build_agent(load_settings()).invoke({"messages": [{"role": "user", "content": (
        "Who are NVIDIA's main competitors in AI accelerators and what are the key industry trends? "
        "Keep it brief."
    )}]})
    calls = [tc for m in result["messages"] if m.type == "ai" for tc in m.tool_calls if tc["name"] == "task"]
    assert {c["args"]["subagent_type"] for c in calls} == {"industry-researcher"}
    assert len(calls) == 1
