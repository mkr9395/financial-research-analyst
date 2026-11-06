"""Tests for the agent factory, prompt and backend (mocked model, no live calls)."""
from datetime import date

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from app import agent as agent_module
from app.agent import build_agent, build_backend
from app.config import PROJECT_ROOT, Settings, load_settings
from app.prompts import manager_prompt


class FakeToolModel(GenericFakeChatModel):
    """Fake chat model that accepts bind_tools so the agent can be built offline."""

    def bind_tools(self, tools, **kwargs):
        return self


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        model="openai:placeholder",
        openai_api_key=SecretStr("sk-test"),
        tavily_api_key=SecretStr("tvly-test"),
        workspace_dir=tmp_path,
        recursion_limit=7,
    )


@pytest.mark.unit
def test_prompt_contains_date_and_planning_instruction():
    prompt = manager_prompt(date(2026, 11, 6))
    assert "2026-11-06" in prompt
    assert "write_todos" in prompt


@pytest.mark.unit
def test_backend_is_confined_to_workspace(settings):
    backend = build_backend(settings)
    assert backend.cwd == settings.workspace_dir.resolve()
    assert backend.virtual_mode is True
    with pytest.raises(ValueError, match="traversal"):
        backend.write("/../outside.md", "x")
    assert not (settings.workspace_dir.parent / "outside.md").exists()


@pytest.mark.unit
def test_build_agent_wiring(settings, monkeypatch):
    captured = {}
    real = agent_module.create_deep_agent

    def spy(**kwargs):
        captured.update(kwargs)
        return real(**{**kwargs, "model": FakeToolModel(messages=iter([]))})

    monkeypatch.setattr(agent_module, "create_deep_agent", spy)
    agent = build_agent(settings)
    assert captured["model"] == "openai:placeholder"
    assert captured["backend"].virtual_mode is True
    assert captured["backend"].cwd == settings.workspace_dir.resolve()
    assert "write_todos" in captured["system_prompt"]
    assert agent.config["recursion_limit"] == 7
    assert [t.name for t in captured["tools"]] == ["web_search"]


@pytest.mark.integration
def test_agent_returns_model_answer(settings, monkeypatch):
    real = agent_module.create_deep_agent
    fake = FakeToolModel(messages=iter([AIMessage(content="hello")]))
    monkeypatch.setattr(agent_module, "create_deep_agent", lambda **kw: real(**{**kw, "model": fake}))
    result = build_agent(settings).invoke({"messages": [{"role": "user", "content": "hi"}]})
    assert result["messages"][-1].text == "hello"


@pytest.mark.e2e
@pytest.mark.live("OPENAI_API_KEY", "MODEL")
def test_live_multi_step_plan_written_to_workspace():
    settings = load_settings()
    target = PROJECT_ROOT / "workspace" / "research" / "plan-test.md"
    target.unlink(missing_ok=True)
    agent = build_agent(settings)
    try:
        result = agent.invoke({"messages": [{"role": "user", "content": (
            "Plan three steps to compare two companies, then write the plan to /research/plan-test.md"
        )}]})
        tool_names = {tc["name"] for m in result["messages"] for tc in getattr(m, "tool_calls", []) or []}
        assert "write_todos" in tool_names
        assert target.exists()
    finally:
        target.unlink(missing_ok=True)
