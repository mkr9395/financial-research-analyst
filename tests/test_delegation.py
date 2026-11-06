"""Live end-to-end tests of manager delegation through the built-in task tool."""
from collections import Counter

import pytest

from app.agent import build_agent
from app.config import load_settings

NAMES = {"financial-researcher", "industry-researcher", "risk-analyst"}
FULL_REQUEST = (
    "Analyze NVIDIA as an investment opportunity. Research its financial performance, "
    "AI business, competitive landscape, and major risks."
)
INDUSTRY_REQUEST = "What are the main competitive trends in the cloud GPU market?"


def execution_path(messages: list) -> list[str]:
    """Return the observed path: manager tool calls in order, and each returned task result."""
    path: list[str] = []
    for m in messages:
        if m.type == "ai":
            for tc in m.tool_calls:
                args = tc["args"]
                if tc["name"] == "write_todos":
                    path.append(f"manager -> write_todos {[t['content'] for t in args.get('todos', [])]}")
                elif tc["name"] == "task":
                    path.append(f"manager -> task[{args.get('subagent_type')}]: {args.get('description', '')[:110]!r}")
                else:
                    path.append(f"manager -> {tc['name']}")
        elif m.type == "tool" and m.name == "task":
            path.append(f"  result ({len(m.content)} chars): {m.content[:110]!r}")
    return path


def _run(request: str) -> tuple[list, list[dict]]:
    result = build_agent(load_settings()).invoke({"messages": [{"role": "user", "content": request}]})
    msgs = result["messages"]
    tasks = [tc for m in msgs if m.type == "ai" for tc in m.tool_calls if tc["name"] == "task"]
    print("\n" + "\n".join(execution_path(msgs)))
    print(f"FINAL: {msgs[-1].text[:300]!r}")
    return msgs, tasks


@pytest.mark.e2e
@pytest.mark.live("OPENAI_API_KEY", "MODEL", "TAVILY_API_KEY")
def test_live_full_analysis_plans_and_delegates_to_all_three_once():
    msgs, tasks = _run(FULL_REQUEST)
    names = [t["args"]["subagent_type"] for t in tasks]
    ai_calls = {tc["name"] for m in msgs if m.type == "ai" for tc in m.tool_calls}
    assert "write_todos" in ai_calls, "no plan written"
    assert set(names) == NAMES, names
    assert max(Counter(names).values()) == 1, f"duplicate task calls: {names}"
    results = [m for m in msgs if m.type == "tool" and m.name == "task"]
    assert len(results) == len(tasks) and all(r.content.strip() for r in results), "empty or missing task results"
    assert "http" in msgs[-1].text


@pytest.mark.e2e
@pytest.mark.live("OPENAI_API_KEY", "MODEL", "TAVILY_API_KEY")
def test_live_industry_question_uses_only_industry_researcher():
    msgs, tasks = _run(INDUSTRY_REQUEST)
    names = [t["args"]["subagent_type"] for t in tasks]
    assert names == ["industry-researcher"], names
    results = [m for m in msgs if m.type == "tool" and m.name == "task"]
    assert len(results) == 1 and results[0].content.strip()


@pytest.mark.integration
def test_manager_delegates_to_specialist_which_searches(tmp_path, monkeypatch):
    from langchain_core.messages import AIMessage
    from pydantic import SecretStr

    from app import agent as agent_module
    from app import tools as tools_module
    from app.config import Settings
    from tests.test_agent import FakeToolModel
    from tests.test_tools import StubClient

    settings = Settings(
        model="openai:placeholder", openai_api_key=SecretStr("sk-test"),
        tavily_api_key=SecretStr("tvly-test"), workspace_dir=tmp_path,
    )
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
