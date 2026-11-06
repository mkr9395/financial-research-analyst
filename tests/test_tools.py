"""Tests for the web_search tool (Tavily stubbed except in the live test)."""
import pytest
from langchain_core.tools import BaseTool, ToolException
from pydantic import SecretStr

from app.config import ConfigError, Settings, load_settings
from app.tools import MAX_RESULTS, MAX_SNIPPET_CHARS, build_web_search_tool


class StubSearch(BaseTool):
    """Stand-in for TavilySearch returning a canned response or raising."""

    name: str = "stub"
    description: str = "stub"
    response: dict | None = None
    error: Exception | None = None
    calls: list = []

    def _run(self, **kwargs):
        return None

    def invoke(self, input, config=None, **kwargs):
        self.calls.append(input)
        if self.error:
            raise self.error
        return self.response


def _settings(tmp_path, key=None) -> Settings:
    return Settings(
        model="openai:x",
        openai_api_key=SecretStr("sk"),
        tavily_api_key=SecretStr(key) if key else None,
        workspace_dir=tmp_path,
    )


def _tool(tmp_path, **stub_kwargs):
    stub = StubSearch(calls=[], **stub_kwargs)
    return build_web_search_tool(_settings(tmp_path), search=stub), stub


@pytest.mark.unit
def test_missing_key_raises_config_error(tmp_path):
    with pytest.raises(ConfigError, match="TAVILY_API_KEY"):
        build_web_search_tool(_settings(tmp_path))


@pytest.mark.unit
def test_tool_schema_is_model_facing(tmp_path):
    tool, _ = _tool(tmp_path, response={"results": []})
    assert tool.name == "web_search"
    assert set(tool.args) == {"query", "topic", "time_range"}
    assert "untrusted" in tool.description.lower()


@pytest.mark.unit
def test_results_are_formatted_and_bounded(tmp_path):
    items = [
        {"title": f"T{i}", "url": f"https://e.com/{i}", "content": "x" * 5000,
         "published_date": "2026-10-01" if i == 0 else None}
        for i in range(MAX_RESULTS + 3)
    ]
    tool, stub = _tool(tmp_path, response={"results": items})
    out = tool.invoke({"query": " nvidia revenue ", "topic": "finance"})
    assert "https://e.com/0" in out and "Published: 2026-10-01" in out
    assert f"[{MAX_RESULTS}]" in out and f"[{MAX_RESULTS + 1}]" not in out
    assert "x" * (MAX_SNIPPET_CHARS + 1) not in out
    assert stub.calls[0]["query"] == "nvidia revenue" and stub.calls[0]["topic"] == "finance"


@pytest.mark.unit
def test_empty_query_is_rejected_without_calling_tavily(tmp_path):
    tool, stub = _tool(tmp_path, response={"results": []})
    assert tool.invoke({"query": "   "}).startswith("Search error")
    assert stub.calls == []


@pytest.mark.unit
def test_no_results_is_reported_to_model(tmp_path):
    tool, _ = _tool(tmp_path, error=ToolException("No search results found for 'q'."))
    assert "Search error: No search results found" in tool.invoke({"query": "q"})


@pytest.mark.unit
def test_api_failure_dict_is_reported_not_hidden(tmp_path):
    tool, _ = _tool(tmp_path, response={"error": ConnectionError("boom")})
    assert "Search error: ConnectionError: boom" in tool.invoke({"query": "q"})


@pytest.mark.integration
def test_agent_calls_web_search_through_tool_node(tmp_path, monkeypatch):
    from langchain_core.messages import AIMessage

    from app import agent as agent_module
    from app import tools as tools_module
    from tests.test_agent import FakeToolModel

    stub = StubSearch(calls=[], response={"results": [{"title": "T", "url": "https://e.com", "content": "c"}]})
    monkeypatch.setattr(tools_module, "TavilySearch", lambda **kw: stub)
    call = AIMessage(content="", tool_calls=[{"name": "web_search", "args": {"query": "nvda"}, "id": "1"}])
    fake = FakeToolModel(messages=iter([call, AIMessage(content="done")]))
    real = agent_module.create_deep_agent
    monkeypatch.setattr(agent_module, "create_deep_agent", lambda **kw: real(**{**kw, "model": fake}))
    result = agent_module.build_agent(_settings(tmp_path, "tvly-test")).invoke(
        {"messages": [{"role": "user", "content": "go"}]}
    )
    tool_msgs = [m for m in result["messages"] if m.type == "tool"]
    assert "https://e.com" in tool_msgs[0].content
    assert stub.calls[0]["query"] == "nvda"


@pytest.mark.live("TAVILY_API_KEY", "OPENAI_API_KEY", "MODEL")
def test_live_search_returns_sourced_results():
    out = build_web_search_tool(load_settings()).invoke(
        {"query": "NVIDIA latest quarterly revenue", "topic": "finance"}
    )
    assert "URL: http" in out and not out.startswith("Search error")
