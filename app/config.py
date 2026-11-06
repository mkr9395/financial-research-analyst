"""Application settings loaded from environment variables (and .env).

Secrets are held as ``SecretStr`` so they never appear in repr, logs or tracebacks.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, SecretStr

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RECURSION_LIMIT = 100
DEFAULT_SEARCH_MAX_RESULTS = 5
DEFAULT_SEARCH_SNIPPET_CHARS = 1000
DEFAULT_LANGSMITH_PROJECT = "deep-financial-research-agent"


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


class Settings(BaseModel):
    """Validated runtime settings."""

    model_config = ConfigDict(frozen=True)

    model: str
    openai_api_key: SecretStr
    tavily_api_key: SecretStr
    langsmith_api_key: SecretStr | None = None
    langsmith_tracing: bool = False
    langsmith_project: str = DEFAULT_LANGSMITH_PROJECT
    workspace_dir: Path = PROJECT_ROOT / "workspace"
    recursion_limit: int = DEFAULT_RECURSION_LIMIT
    search_max_results: int = DEFAULT_SEARCH_MAX_RESULTS
    search_snippet_chars: int = DEFAULT_SEARCH_SNIPPET_CHARS


def _optional_secret(name: str) -> SecretStr | None:
    value = os.environ.get(name, "").strip()
    return SecretStr(value) if value else None


def _positive_int(name: str, default: int) -> int:
    """Read an integer env var that must be at least 1."""
    try:
        value = int(os.environ.get(name, default))
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer.") from exc
    if value < 1:
        raise ConfigError(f"{name} must be at least 1.")
    return value


def load_settings() -> Settings:
    """Load settings from the environment; fail fast with a clear message.

    Tracing is enabled only when LANGSMITH_TRACING is "true" AND a LangSmith key
    is set. Otherwise it is explicitly switched off so the app works either way.
    """
    load_dotenv(PROJECT_ROOT / ".env")

    openai_key = _optional_secret("OPENAI_API_KEY")
    if openai_key is None:
        raise ConfigError("OPENAI_API_KEY is not set. Add it to .env (see .env.example).")

    tavily_key = _optional_secret("TAVILY_API_KEY")
    if tavily_key is None:
        raise ConfigError("TAVILY_API_KEY is not set. Add it to .env; web search needs it.")

    model = os.environ.get("MODEL", "").strip()
    if ":" not in model:
        raise ConfigError("MODEL must be set in provider:model form, e.g. openai:<model-name>.")

    langsmith_key = _optional_secret("LANGSMITH_API_KEY")
    wants_tracing = os.environ.get("LANGSMITH_TRACING", "").strip().lower() == "true"
    tracing = wants_tracing and langsmith_key is not None
    os.environ["LANGSMITH_TRACING"] = "true" if tracing else "false"

    return Settings(
        model=model,
        openai_api_key=openai_key,
        tavily_api_key=tavily_key,
        langsmith_api_key=langsmith_key,
        langsmith_tracing=tracing,
        langsmith_project=os.environ.get("LANGSMITH_PROJECT", "").strip()
        or DEFAULT_LANGSMITH_PROJECT,
        recursion_limit=_positive_int("RECURSION_LIMIT", DEFAULT_RECURSION_LIMIT),
        search_max_results=_positive_int("SEARCH_MAX_RESULTS", DEFAULT_SEARCH_MAX_RESULTS),
        search_snippet_chars=_positive_int(
            "SEARCH_SNIPPET_CHARS", DEFAULT_SEARCH_SNIPPET_CHARS
        ),
    )
