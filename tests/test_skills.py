"""Tests for runtime skills in workspace/skills/ (offline; the model is faked)."""
import pytest
from deepagents.backends import FilesystemBackend
from deepagents.middleware.skills import _list_skills_with_errors
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from app import agent as agent_module
from app.agent import SKILLS_SOURCE, build_agent
from app.config import PROJECT_ROOT, Settings
from tests.test_agent import FakeToolModel

EXPECTED = {"financial-analysis", "investment-research", "risk-analysis"}
WORKSPACE = PROJECT_ROOT / "workspace"


@pytest.mark.unit
def test_runtime_skills_load_without_errors():
    backend = FilesystemBackend(root_dir=WORKSPACE, virtual_mode=True)
    skills, error = _list_skills_with_errors(backend, SKILLS_SOURCE)
    assert error is None
    assert {s["name"] for s in skills} == EXPECTED
    assert all(s["description"] for s in skills)


@pytest.mark.unit
def test_skills_source_is_passed_to_agent(tmp_path, monkeypatch):
    captured = {}
    real = agent_module.create_deep_agent

    def spy(**kwargs):
        captured.update(kwargs)
        return real(**{**kwargs, "model": FakeToolModel(messages=iter([]))})

    monkeypatch.setattr(agent_module, "create_deep_agent", spy)
    build_agent(_settings(tmp_path))
    assert captured["skills"] == ["/skills/"]


def _settings(path) -> Settings:
    return Settings(
        model="openai:placeholder",
        openai_api_key=SecretStr("sk-test"),
        tavily_api_key=SecretStr("tvly-test"),
        workspace_dir=path,
    )


@pytest.mark.integration
def test_skill_names_reach_the_model_prompt(monkeypatch):
    """The real skills directory is listed in the system prompt the model receives."""
    seen = []

    class Spy(FakeToolModel):
        def _generate(self, messages, *args, **kwargs):
            seen.append(messages[0].text)
            return super()._generate(messages, *args, **kwargs)

    fake = Spy(messages=iter([AIMessage(content="ok")]))
    real = agent_module.create_deep_agent
    monkeypatch.setattr(agent_module, "create_deep_agent", lambda **kw: real(**{**kw, "model": fake}))
    settings = _settings(WORKSPACE)
    build_agent(settings).invoke({"messages": [{"role": "user", "content": "hi"}]})
    prompt = seen[0]
    skills, _ = _list_skills_with_errors(FilesystemBackend(root_dir=WORKSPACE, virtual_mode=True), SKILLS_SOURCE)
    assert all(s["name"] in prompt and s["description"] in prompt for s in skills)
    # Progressive disclosure: the SKILL.md bodies are not in the prompt.
    for marker in ("Reporting period rule", "Build the view", "Categories to check"):
        assert marker not in prompt


@pytest.mark.e2e
@pytest.mark.live("OPENAI_API_KEY", "MODEL", "TAVILY_API_KEY")
def test_live_agent_reads_matching_skill():
    from app.config import load_settings

    result = build_agent(load_settings()).invoke({"messages": [{"role": "user", "content": (
        "Use your skill for rating company risks. Then state in one line how risks "
        "should be rated."
    )}]})
    calls = [tc for m in result["messages"] for tc in getattr(m, "tool_calls", []) or []]
    assert any(tc["name"] == "read_file" and "/skills/risk-analysis" in str(tc["args"]) for tc in calls)
