"""Unit tests for app.config (no network, no real LLM)."""
import pytest

from app import config
from app.config import ConfigError, load_settings

ENV_NAMES = (
    "OPENAI_API_KEY", "MODEL", "TAVILY_API_KEY", "LANGSMITH_API_KEY",
    "LANGSMITH_TRACING", "LANGSMITH_PROJECT", "RECURSION_LIMIT",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Isolate from the developer's real .env and environment."""
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: None)
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def base_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")
    monkeypatch.setenv("MODEL", "openai:test-model")


@pytest.mark.unit
def test_defaults(base_env):
    s = load_settings()
    assert s.model == "openai:test-model"
    assert s.recursion_limit == 100
    assert s.langsmith_tracing is False
    assert s.tavily_api_key is None
    assert s.workspace_dir.name == "workspace"


@pytest.mark.unit
def test_missing_openai_key_fails_fast(monkeypatch):
    monkeypatch.setenv("MODEL", "openai:test-model")
    with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
        load_settings()


@pytest.mark.unit
def test_model_must_have_provider(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")
    monkeypatch.setenv("MODEL", "bare-name")
    with pytest.raises(ConfigError, match="provider:model"):
        load_settings()


@pytest.mark.unit
def test_secrets_not_exposed(base_env):
    s = load_settings()
    assert "sk-test-secret" not in repr(s)
    assert "sk-test-secret" not in str(s)


@pytest.mark.unit
def test_tracing_off_without_key(base_env, monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    s = load_settings()
    assert s.langsmith_tracing is False
    assert config.os.environ["LANGSMITH_TRACING"] == "false"


@pytest.mark.unit
def test_tracing_on_with_key_and_project(base_env, monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls-test")
    monkeypatch.setenv("LANGSMITH_PROJECT", "my-project")
    s = load_settings()
    assert s.langsmith_tracing is True
    assert s.langsmith_project == "my-project"


@pytest.mark.unit
def test_recursion_limit_setting_and_validation(base_env, monkeypatch):
    monkeypatch.setenv("RECURSION_LIMIT", "40")
    assert load_settings().recursion_limit == 40
    monkeypatch.setenv("RECURSION_LIMIT", "abc")
    with pytest.raises(ConfigError, match="RECURSION_LIMIT"):
        load_settings()
    monkeypatch.setenv("RECURSION_LIMIT", "0")
    with pytest.raises(ConfigError, match="RECURSION_LIMIT"):
        load_settings()
