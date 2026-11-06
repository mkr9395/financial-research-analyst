"""Tests for research artifacts: prompts, writing through the shared backend, and a live NVIDIA run."""
from datetime import date

import pytest
from pydantic import SecretStr

from app.backend import build_backend
from app.config import Settings, load_settings
from app.prompts import manager_prompt
from app.subagents import SPECIALISTS, build_subagents
from tests.test_delegation import FULL_REQUEST, _run
from tests.test_subagents import search_tool, settings  # noqa: F401  (fixtures)

REQUIRED = ("## Findings", "## Key evidence", "## Sources", "## Uncertainty and gaps", "Research date:")
PATHS = {
    "financial-researcher": "/research/financial.md",
    "industry-researcher": "/research/industry.md",
    "risk-analyst": "/research/risks.md",
}


def missing_sections(text: str) -> list[str]:
    """Return the required artifact sections absent from text."""
    return [s for s in REQUIRED if s not in text]


@pytest.mark.unit
def test_missing_sections_helper():
    good = "\n".join(REQUIRED)
    assert missing_sections(good) == []
    assert missing_sections(good.replace("## Sources", "")) == ["## Sources"]
    assert missing_sections("") == list(REQUIRED)


@pytest.mark.unit
def test_specialist_prompts_require_artifact_and_short_reply(search_tool):  # noqa: F811
    for s in build_subagents(search_tool, date(2026, 11, 6)):
        p = s["system_prompt"]
        assert PATHS[s["name"]] in p
        for section in REQUIRED:
            assert section.removeprefix("## ").removesuffix(":") in p
        assert "150 words" in p and "at most 200 words" in p and "write_file" in p
        assert "Do not write files" not in p
    assert {d["artifact"] for d in SPECIALISTS} == set(PATHS.values())


@pytest.mark.unit
def test_manager_prompt_artifact_rules():
    p = manager_prompt(date(2026, 11, 6))
    for path in PATHS.values():
        assert path in p
    assert "Do NOT read these files by default" in p
    assert "re-delegate ONCE" in p and "report the gap" in p


@pytest.mark.integration
def test_backend_write_lands_in_workspace_research(settings):  # noqa: F811
    result = build_backend(settings).write("/research/financial.md", "\n".join(REQUIRED))
    assert result.error is None
    assert (settings.workspace_dir / "research" / "financial.md").is_file()


@pytest.mark.e2e
@pytest.mark.live("OPENAI_API_KEY", "MODEL", "TAVILY_API_KEY")
def test_live_nvidia_run_writes_three_valid_artifacts_and_short_task_results():
    workspace = load_settings().workspace_dir / "research"
    msgs, _ = _run(FULL_REQUEST)
    for path in PATHS.values():
        f = workspace / path.rsplit("/", 1)[1]
        assert f.is_file(), f"{f} missing"
        assert missing_sections(f.read_text(encoding="utf-8")) == [], f
    for path in PATHS.values():
        words = len((workspace / path.rsplit("/", 1)[1]).read_text(encoding="utf-8").split())
        print(f"{path}: {words} words")
        assert words <= 220, f"{path} has {words} words (limit 200, 220 tolerance)"
    results = [m for m in msgs if m.type == "tool" and m.name == "task"]
    assert results and all(len(r.content) < 1500 for r in results), [len(r.content) for r in results]
    for r in results:
        print(f"task result {len(r.content)} chars")
    for path in PATHS.values():
        print(f"{path}: {(workspace / path.rsplit('/', 1)[1]).stat().st_size} bytes")
