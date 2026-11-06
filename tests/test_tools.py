"""Tests for the web_search tool (Tavily stubbed except in the live test)."""
import pytest
import requests
from tavily import InvalidAPIKeyError, UsageLimitExceededError
from tavily.errors import TimeoutError as TavilyTimeout
from pydantic import SecretStr

from app import config
from app.config import ConfigError, Settings, load_settings
from app.tools import build_web_search_tool


class StubClient:
    """Stand-in for tavily.TavilyClient returning a canned response or raising."""

    def __init__(self, response: dict | None = None, error: Exception | None = None):
        self.response, self.error, self.calls = response, error, []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def _settings(tmp_path, key="tvly-test", **limits) -> Settings:
    return Settings(
        model="openai:x",
        openai_api_key=SecretStr("sk"),
        tavily_api_key=SecretStr(key),
        workspace_dir=tmp_path,
        **limits,
    )


def _tool(tmp_path, limits=None, **stub_kwargs):
    stub = StubClient(**stub_kwargs)
    return build_web_search_tool(_settings(tmp_path, **(limits or {})), client=stub), stub


@pytest.mark.unit
def test_missing_tavily_key_fails_at_config_load(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("MODEL", "openai:x")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with pytest.raises(ConfigError, match="TAVILY_API_KEY"):
        load_settings()


@pytest.mark.unit
def test_tool_schema_is_model_facing(tmp_path):
    tool, _ = _tool(tmp_path, response={"results": []})
    assert tool.name == "web_search"
    assert set(tool.args) == {"query", "topic", "time_range"}
    assert "untrusted" in tool.description.lower()


@pytest.mark.unit
def test_results_are_normalised_and_bounded(tmp_path):
    max_results, snippet_chars = 3, 50
    items = [
        {"title": f"T{i}", "url": f"https://e.com/{i}", "content": "x" * 5000,
         "published_date": "2026-10-01" if i == 0 else None}
        for i in range(max_results + 4)
    ]
    tool, stub = _tool(
        tmp_path,
        limits={"search_max_results": max_results, "search_snippet_chars": snippet_chars},
        response={"results": items},
    )
    out = tool.invoke({"query": " nvidia revenue ", "topic": "finance"})
    assert "https://e.com/0" in out and "Published: 2026-10-01" in out
    assert f"[{max_results}]" in out and f"[{max_results + 1}]" not in out
    assert "x" * snippet_chars in out and "x" * (snippet_chars + 1) not in out
    assert "Published:" not in out.split("[2]")[1]  # date shown only when available
    assert stub.calls[0]["query"] == "nvidia revenue" and stub.calls[0]["topic"] == "finance"


@pytest.mark.unit
def test_empty_query_is_rejected_without_calling_tavily(tmp_path):
    tool, stub = _tool(tmp_path, response={"results": []})
    assert tool.invoke({"query": "   "}).startswith("Search error")
    assert stub.calls == []


@pytest.mark.unit
def test_empty_result_list_is_explicit(tmp_path):
    tool, _ = _tool(tmp_path, response={"results": []})
    assert tool.invoke({"query": "zzz"}) == "No results found for 'zzz'."


@pytest.mark.unit
@pytest.mark.parametrize(
    "error, expected",
    [
        (TavilyTimeout(30), "Search error (TimeoutError): Request timed out after 30 seconds."),
        (InvalidAPIKeyError("Unauthorized"), "Search error (InvalidAPIKeyError): Unauthorized"),
        (UsageLimitExceededError("rate limit"), "Search error (UsageLimitExceededError): rate limit"),
        (requests.ConnectionError("boom"), "Search error (ConnectionError): boom"),
    ],
)
def test_known_api_failures_are_reported_to_model(tmp_path, error, expected):
    tool, _ = _tool(tmp_path, error=error)
    assert tool.invoke({"query": "q"}) == expected


@pytest.mark.unit
def test_unexpected_errors_are_not_swallowed(tmp_path):
    tool, _ = _tool(tmp_path, error=RuntimeError("bug"))
    with pytest.raises(RuntimeError, match="bug"):
        tool.invoke({"query": "q"})


@pytest.mark.integration
def test_agent_calls_web_search_through_tool_node(tmp_path, monkeypatch):
    from langchain_core.messages import AIMessage

    from app import agent as agent_module
    from app import tools as tools_module
    from tests.test_agent import FakeToolModel

    stub = StubClient(response={"results": [{"title": "T", "url": "https://e.com", "content": "c"}]})
    monkeypatch.setattr(tools_module, "TavilyClient", lambda **kw: stub)
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


@pytest.mark.integration
@pytest.mark.live("TAVILY_API_KEY", "OPENAI_API_KEY", "MODEL")
def test_live_search_returns_sourced_results():
    out = build_web_search_tool(load_settings()).invoke(
        {"query": "NVIDIA latest quarterly revenue", "topic": "finance"}
    )
    assert "URL: http" in out and not out.startswith("Search error")


@pytest.mark.e2e
@pytest.mark.live("TAVILY_API_KEY", "OPENAI_API_KEY", "MODEL")
def test_live_agent_searches_and_cites_a_url():
    from app.agent import build_agent

    result = build_agent(load_settings()).invoke(
        {"messages": [{"role": "user", "content":
            "What was NVIDIA's most recent quarterly revenue? Cite the source."}]}
    )
    messages = result["messages"]
    searches = [c for m in messages if m.type == "ai" for c in m.tool_calls if c["name"] == "web_search"]
    assert searches, "agent never called web_search"
    tool_output = " ".join(m.content for m in messages if m.type == "tool" and m.name == "web_search")
    assert "URL: http" in tool_output, f"search did not return results: {tool_output[:200]}"
    assert "http" in messages[-1].text, "final answer cites no URL"
