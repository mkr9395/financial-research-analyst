# Dev log

## Session 1 - Project foundation

**Built**
- Environment check: Python 3.11.9, `.venv` active, git repo on `main`; no project packages installed.
- Project structure: `app/`, `tests/`, `workspace/` (skills, memories committed; research, reports git-ignored), `docs/`, `.claude/`.
- `.claude/settings.json` denying reads of `.env`; Claude Code skills `deep-agent-development` and `testing`; read-only subagent `architecture-reviewer` (classifies findings MUST FIX / SHOULD FIX / POC ACCEPTABLE / PRODUCTION ONLY).
- `CLAUDE.md` (purpose, scope, architecture, fixed design decisions, standards, security, testing, workflow, debugging protocol, end-of-session procedure).
- `docs/architecture.md` (manager, three specialists, search tool, skills, workspace layout, memory, approval tool, structured output, LangSmith).
- `pytest.ini` with markers unit/integration/e2e/live; `tests/conftest.py` auto-skipping `live` tests when keys are missing; `.env.example`; unpinned `requirements.txt`.

**Key decisions and why**
- Single `FilesystemBackend` rooted at `workspace/` with `virtual_mode=True`: docs state that without it there is no real path confinement.
- Orchestration only via built-in Deep Agents features (`task`, todos, `interrupt_on`); no custom graph or middleware, to keep the POC small.
- Human approval through `interrupt_on` on `submit_draft_assessment` with a checkpointer, not `input()`.
- Three specialists (Financial Researcher, Industry Researcher, Risk Analyst), each writing `/research/<area>.md` and returning a short summary.
- `.env` protected by a `Read` deny rule (Bash deny rules are best-effort only).
- Dev skills (`.claude/skills/`) kept separate from runtime skills (`workspace/skills/`).

**Problems and fixes**
- Debugging protocol was missing from the original prompt; a placeholder was written, then replaced with the supplied 12-step protocol.
- `CLAUDE.md` named four specialists while the architecture has three; corrected to three.
- Docs-based facts for `deepagents` could not be checked against an installed package; unconfirmed items are marked VERIFY / *to verify* for Session 2.
- Docs note framework-internal files may be written under `workspace/`, which sits uneasily with the single-backend decision; deferred.

**Test results**
- No tests exist yet and pytest is not installed in the venv, so nothing was run: 0 passed, 0 failed, 0 skipped. The `live` auto-skip logic in `conftest.py` is therefore untested.

**Checkpoint status**
- No checkpoint was defined for this session. Against the Session 1 deliverables (structure, config, docs, no application code) all items are present; the test-based verification is outstanding.
