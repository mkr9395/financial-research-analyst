"""Application settings loaded from environment variables (and .env).

Secrets are held as ``SecretStr`` so they never appear in repr, logs or tracebacks.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, SecretStr

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RECURSION_LIMIT = 100
DEFAULT_LANGSMITH_PROJECT = "deep-financial-research-agent"


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


class Settings(BaseModel):
    """Validated runtime settings."""

    model_config = ConfigDict(frozen=True)

    model: str
    openai_api_key: SecretStr
    tavily_api_key: SecretStr | None = None
    langsmith_api_key: SecretStr | None = None
    langsmith_tracing: bool = False
    langsmith_project: str = DEFAULT_LANGSMITH_PROJECT
    workspace_dir: Path = PROJECT_ROOT / "workspace"
    recursion_limit: int = DEFAULT_RECURSION_LIMIT


def _optional_secret(name: str) -> SecretStr | None:
    value = os.environ.get(name, "").strip()
    return SecretStr(value) if value else None


def load_settings() -> Settings:
    """Load settings from the environment; fail fast with a clear message.

    Tracing is enabled only when LANGSMITH_TRACING is "true" AND a LangSmith key
    is set. Otherwise it is explicitly switched off so the app works either way.
    """
    load_dotenv(PROJECT_ROOT / ".env")

    openai_key = _optional_secret("OPENAI_API_KEY")
    if openai_key is None:
        raise ConfigError("OPENAI_API_KEY is not set. Add it to .env (see .env.example).")

    model = os.environ.get("MODEL", "").strip()
    if ":" not in model:
        raise ConfigError("MODEL must be set in provider:model form, e.g. openai:<model-name>.")

    langsmith_key = _optional_secret("LANGSMITH_API_KEY")
    wants_tracing = os.environ.get("LANGSMITH_TRACING", "").strip().lower() == "true"
    tracing = wants_tracing and langsmith_key is not None
    os.environ["LANGSMITH_TRACING"] = "true" if tracing else "false"

    try:
        recursion_limit = int(os.environ.get("RECURSION_LIMIT", DEFAULT_RECURSION_LIMIT))
    except ValueError as exc:
        raise ConfigError("RECURSION_LIMIT must be an integer.") from exc
    if recursion_limit < 1:
        raise ConfigError("RECURSION_LIMIT must be at least 1.")

    return Settings(
        model=model,
        openai_api_key=openai_key,
        tavily_api_key=_optional_secret("TAVILY_API_KEY"),
        langsmith_api_key=langsmith_key,
        langsmith_tracing=tracing,
        langsmith_project=os.environ.get("LANGSMITH_PROJECT", "").strip()
        or DEFAULT_LANGSMITH_PROJECT,
        recursion_limit=recursion_limit,
    )
