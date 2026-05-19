"""Tests for stepped-workflow parsing and step files."""
from __future__ import annotations

import pytest

from lib import step as _step


STEP_TEXT = """# Step 1: Initialize

<step-meta>
number: 1
name: initialize
gate: false
next: step-02-context
repo: $all
skill: superpowers:brainstorming
requires_skill: false
</step-meta>

<purpose>
Establish initial framing.
</purpose>

<instructions>
1. Read the spec.
2. Identify constraints.
</instructions>

<output>
A short framing summary.
</output>
"""


def test_parse_step_meta():
    s = _step.parse_step_text(STEP_TEXT)
    assert s.number == 1
    assert s.name == "initialize"
    assert s.gate is False
    assert s.next == "step-02-context"
    assert s.repo == "$all"
    assert s.skill == "superpowers:brainstorming"
    assert s.requires_skill is False


def test_parse_step_sections():
    s = _step.parse_step_text(STEP_TEXT)
    assert "Establish initial framing" in s.purpose
    assert "Read the spec" in s.instructions
    assert "framing summary" in s.output


def test_parse_step_with_gate():
    text = STEP_TEXT.replace("gate: false", "gate: true") + """
<gate>
## Completion criteria
- [ ] Spec read
</gate>
"""
    s = _step.parse_step_text(text)
    assert s.gate is True
    assert "Completion criteria" in (s.gate_text or "")


def test_parse_step_missing_meta_raises():
    bad = STEP_TEXT.replace("<step-meta>", "<mtea>")
    with pytest.raises(_step.StepSchemaError, match="step-meta"):
        _step.parse_step_text(bad)
