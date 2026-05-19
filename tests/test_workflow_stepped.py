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


def test_stepped_workflow_loads_with_steps_dir(tmp_path):
    from lib import workflow as _wf
    (tmp_path / "myflow").mkdir()
    (tmp_path / "myflow" / "steps").mkdir()
    (tmp_path / "myflow" / "steps" / "step-01-init.md").write_text(STEP_TEXT)
    (tmp_path / "myflow" / "steps" / "step-02-finish.md").write_text(
        STEP_TEXT.replace("number: 1", "number: 2")
                 .replace("name: initialize", "name: finish")
                 .replace("next: step-02-context", "next: null")
    )
    (tmp_path / "myflow.yaml").write_text("""
workflow:
  name: myflow
  type: stepped
  agent: architect
  steps:
    path: ./myflow/steps/
    pattern: 'step-{nn}-*.md'
""")
    from pathlib import Path as _P
    plugin_root = _P(__file__).resolve().parent.parent
    wf = _wf.load_workflow_file(tmp_path / "myflow.yaml", plugin_root=plugin_root)
    assert wf.type == "stepped"
    assert wf.agent == "architect"
    assert wf.steps is not None
    assert len(wf.steps) == 2
    assert wf.steps[0].name == "initialize"


def test_stepped_workflow_rejects_expansion_field(tmp_path):
    from lib import workflow as _wf
    (tmp_path / "myflow.yaml").write_text("""
workflow:
  name: myflow
  type: stepped
  agent: architect
  expansion: per-repo
  steps:
    path: ./myflow/steps/
""")
    import pytest
    from pathlib import Path as _P
    plugin_root = _P(__file__).resolve().parent.parent
    with pytest.raises(_wf.WorkflowSchemaError, match="expansion"):
        _wf.load_workflow_file(tmp_path / "myflow.yaml", plugin_root=plugin_root)
