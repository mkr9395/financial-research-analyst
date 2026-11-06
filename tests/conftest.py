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


def _missing_keys(required: tuple[str, ...]) -> list[str]:
    return [k for k in required if not os.environ.get(k)]


def pytest_collection_modifyitems(config, items):
    """Skip live tests lacking keys. ``@pytest.mark.live("KEY", ...)`` narrows the keys."""
    for item in items:
        marker = item.get_closest_marker("live")
        if marker is None:
            continue
        missing = _missing_keys(tuple(marker.args) or REQUIRED_LIVE_KEYS)
        if missing:
            item.add_marker(
                pytest.mark.skip(
                    reason=f"live test skipped: missing env var(s) {', '.join(missing)}"
                )
            )
