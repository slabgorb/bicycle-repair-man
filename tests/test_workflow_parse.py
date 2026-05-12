"""Unit tests for lib/workflow.py."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from lib.workflow import (
    Workflow,
    WorkflowPhase,
    WorkflowSchemaError,
    expand_phases,
    load_workflow,
    validate_workflow,
)

VALID_TDD = textwrap.dedent("""\
    workflow:
      name: tdd
      description: TDD across one or more repos
      version: "1.0.0"
      expansion: per-repo
      phases:
        - name: red
          agent: tea
          repo: $each
          gate:
            file: gates/tests-fail
        - name: green
          agent: dev
          repo: $each
          gate:
            file: gates/tests-pass
        - name: review
          agent: reviewer
          repos: $all
          gate:
            file: gates/approval
        - name: finish
          agent: pm
""")


def _write_workflow(root: Path, name: str, content: str) -> Path:
    p = root / "workflows" / f"{name}.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


def test_load_workflow_from_plugin_root(tmp_path: Path):
    _write_workflow(tmp_path, "tdd", VALID_TDD)
    wf = load_workflow("tdd", plugin_root=tmp_path)
    assert wf.name == "tdd"
    assert len(wf.phases) == 4
    assert wf.phases[0].name == "red"
    assert wf.phases[0].agent == "tea"
    assert wf.phases[0].repo == "$each"
    assert wf.phases[2].repos == "$all"
    assert wf.phases[3].repo is None and wf.phases[3].repos is None


def test_load_workflow_orchestrator_overrides_plugin(tmp_path: Path):
    plugin = tmp_path / "plugin"
    orch = tmp_path / "orch"
    _write_workflow(plugin, "tdd", VALID_TDD)
    _write_workflow(orch / ".brm", "tdd", VALID_TDD.replace("TDD across", "OVERRIDE"))
    wf = load_workflow("tdd", plugin_root=plugin, orchestrator_root=orch)
    assert wf.description == "OVERRIDE one or more repos"


def test_load_workflow_not_found(tmp_path: Path):
    with pytest.raises(WorkflowSchemaError, match="not found"):
        load_workflow("nope", plugin_root=tmp_path)


def test_validate_rejects_invalid_agent(tmp_path: Path):
    bad = VALID_TDD.replace("agent: tea", "agent: nope")
    _write_workflow(tmp_path, "tdd", bad)
    with pytest.raises(WorkflowSchemaError, match="agent"):
        load_workflow("tdd", plugin_root=tmp_path)


def test_validate_rejects_repo_and_repos_both(tmp_path: Path):
    bad = textwrap.dedent("""\
        workflow:
          name: tdd
          expansion: per-repo
          phases:
            - name: red
              agent: tea
              repo: api
              repos: [api, ui]
              gate: {file: gates/tests-fail}
            - name: finish
              agent: pm
    """)
    _write_workflow(tmp_path, "tdd", bad)
    with pytest.raises(WorkflowSchemaError, match="repo.*repos"):
        load_workflow("tdd", plugin_root=tmp_path)


def test_validate_rejects_each_on_repos(tmp_path: Path):
    bad = textwrap.dedent("""\
        workflow:
          name: tdd
          expansion: per-repo
          phases:
            - name: red
              agent: tea
              repos: $each
              gate: {file: gates/tests-fail}
            - name: finish
              agent: pm
    """)
    _write_workflow(tmp_path, "tdd", bad)
    with pytest.raises(WorkflowSchemaError, match="\\$each"):
        load_workflow("tdd", plugin_root=tmp_path)


def test_validate_rejects_reserved_expansion(tmp_path: Path):
    bad = VALID_TDD.replace("expansion: per-repo", "expansion: as-written")
    _write_workflow(tmp_path, "tdd", bad)
    with pytest.raises(WorkflowSchemaError, match="as-written"):
        load_workflow("tdd", plugin_root=tmp_path)


def test_validate_duplicate_phase_names(tmp_path: Path):
    bad = textwrap.dedent("""\
        workflow:
          name: tdd
          expansion: per-repo
          phases:
            - name: red
              agent: tea
              repo: api
              gate: {file: gates/tests-fail}
            - name: red
              agent: dev
              repo: api
    """)
    _write_workflow(tmp_path, "tdd", bad)
    with pytest.raises(WorkflowSchemaError, match="duplicate"):
        load_workflow("tdd", plugin_root=tmp_path)


def test_expand_each_single_repo(tmp_path: Path):
    _write_workflow(tmp_path, "tdd", VALID_TDD)
    wf = load_workflow("tdd", plugin_root=tmp_path)
    expanded = expand_phases(wf, ["api"])
    names = [p.name for p in expanded]
    assert names == ["red-api", "green-api", "review", "finish"]
    red = expanded[0]
    assert red.repo == "api"
    assert red.repos is None


def test_expand_each_multi_repo(tmp_path: Path):
    _write_workflow(tmp_path, "tdd", VALID_TDD)
    wf = load_workflow("tdd", plugin_root=tmp_path)
    expanded = expand_phases(wf, ["api", "ui"])
    names = [p.name for p in expanded]
    assert names == ["red-api", "red-ui", "green-api", "green-ui", "review", "finish"]
    assert expanded[0].repo == "api"
    assert expanded[1].repo == "ui"


def test_expand_all_substitutes_repos_list(tmp_path: Path):
    _write_workflow(tmp_path, "tdd", VALID_TDD)
    wf = load_workflow("tdd", plugin_root=tmp_path)
    expanded = expand_phases(wf, ["api", "ui"])
    review = [p for p in expanded if p.name == "review"][0]
    assert review.repos == ["api", "ui"]
    assert review.repo is None


def test_expand_unscoped_passes_through(tmp_path: Path):
    _write_workflow(tmp_path, "tdd", VALID_TDD)
    wf = load_workflow("tdd", plugin_root=tmp_path)
    expanded = expand_phases(wf, ["api"])
    finish = expanded[-1]
    assert finish.name == "finish"
    assert finish.repo is None
    assert finish.repos is None


def test_expand_preserves_gate_per_phase(tmp_path: Path):
    _write_workflow(tmp_path, "tdd", VALID_TDD)
    wf = load_workflow("tdd", plugin_root=tmp_path)
    expanded = expand_phases(wf, ["api", "ui"])
    for p in expanded[:2]:
        assert p.gate is not None and p.gate.file == "gates/tests-fail"


def test_expand_rejects_empty_repos(tmp_path: Path):
    _write_workflow(tmp_path, "tdd", VALID_TDD)
    wf = load_workflow("tdd", plugin_root=tmp_path)
    with pytest.raises(WorkflowSchemaError, match="empty"):
        expand_phases(wf, [])
