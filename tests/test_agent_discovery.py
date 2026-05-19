"""Tests for agent file parsing and discovery."""
from __future__ import annotations

import pytest

from lib import agent as _agent

AGENT_TEXT = """# Reviewer — adversarial code review

<persona>
Default reviewer persona.
</persona>

<role>
**Kind:** tactical
**Primary:** Adversarial code review after green tests.
</role>

<helpers>
- reviewer-security
- reviewer-edge-hunter
</helpers>

<responsibilities>
- Find issues by severity.
- Cite specific files and lines.
</responsibilities>

<skills>
**Anchor skill (default):** `superpowers:requesting-code-review`
</skills>

<context>
Sidecar: `.brm/sidecars/reviewer.md`
</context>

<on-activation>
1. Read injected blocks.
2. Begin adversarial pass.
</on-activation>

## Workflows

(free-form)

<handoff>
Write a handoff with severity buckets.
</handoff>

<exit>
Another role activates.
</exit>
"""


def test_parse_agent_extracts_kind():
    a = _agent.parse_agent_text(AGENT_TEXT, name="reviewer")
    assert a.name == "reviewer"
    assert a.kind == "tactical"


def test_parse_agent_extracts_anchor_skill():
    a = _agent.parse_agent_text(AGENT_TEXT, name="reviewer")
    assert a.anchor_skill == "superpowers:requesting-code-review"


def test_parse_agent_extracts_helpers():
    a = _agent.parse_agent_text(AGENT_TEXT, name="reviewer")
    assert "reviewer-security" in a.helpers
    assert "reviewer-edge-hunter" in a.helpers


def test_parse_agent_missing_role_section_raises():
    bad = AGENT_TEXT.replace("<role>", "<rol>")  # mangle
    with pytest.raises(_agent.AgentSchemaError, match="role"):
        _agent.parse_agent_text(bad, name="reviewer")


def test_parse_agent_unknown_kind_raises():
    bad = AGENT_TEXT.replace("**Kind:** tactical", "**Kind:** nonsense")
    with pytest.raises(_agent.AgentSchemaError, match="kind"):
        _agent.parse_agent_text(bad, name="reviewer")


def test_strategic_template_parses_and_has_required_tags():
    from pathlib import Path
    text = (Path(__file__).resolve().parent.parent / "agents" / "templates" / "strategic.md").read_text()
    # Templates have placeholder name; parse with a fixed name
    a = _agent.parse_agent_text(text, name="template-strategic")
    assert a.kind == "strategic"
    for tag in ("persona", "role", "responsibilities", "skills", "context",
                "on-activation", "handoff", "exit"):
        assert f"<{tag}>" in text


def test_tactical_template_parses_and_has_required_tags():
    from pathlib import Path
    text = (Path(__file__).resolve().parent.parent / "agents" / "templates" / "tactical.md").read_text()
    a = _agent.parse_agent_text(text, name="template-tactical")
    assert a.kind == "tactical"
