"""Shared pytest configuration.

Tests marked ``live`` call real APIs and are skipped automatically when the
required API keys are not set. Only presence is checked, never the value.
"""
import os

import pytest

try:  # optional: load .env into the process environment if python-dotenv exists
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

REQUIRED_LIVE_KEYS = ("OPENAI_API_KEY", "TAVILY_API_KEY")


def _missing_keys() -> list[str]:
    return [k for k in REQUIRED_LIVE_KEYS if not os.environ.get(k)]


def pytest_collection_modifyitems(config, items):
    missing = _missing_keys()
    if not missing:
        return
    skip_live = pytest.mark.skip(
        reason=f"live test skipped: missing env var(s) {', '.join(missing)}"
    )
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
