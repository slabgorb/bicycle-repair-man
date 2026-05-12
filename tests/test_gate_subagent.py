"""Unit tests for lib/gate.py — no LLM invoked."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from lib.gate import (
    Gate,
    GateContext,
    GateResultError,
    parse_gate_file,
    render_gate_prompt,
    parse_gate_result,
)

SIMPLE_GATE = textwrap.dedent("""\
    <gate name="tests-pass" model="haiku">

    <purpose>
    Verify tests pass in ${repo.path}.
    </purpose>

    <pass>
    Tests passing in ${repo.path}.

    GATE_RESULT:
      status: pass
      gate: tests-pass
      repo: ${phase.repo}
      message: "Tests passing in ${phase.repo}"
    </pass>

    <fail>
    Tests failing in ${repo.path}.

    GATE_RESULT:
      status: fail
      gate: tests-pass
      message: "Tests failing"
      recovery:
        - "Fix failing tests in ${repo.path}"
    </fail>

    </gate>
""")


def _write_gate(root: Path, name: str, text: str) -> Path:
    p = root / "gates" / f"{name}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def test_parse_gate_file_extracts_metadata(tmp_path: Path):
    p = _write_gate(tmp_path, "tests-pass", SIMPLE_GATE)
    g = parse_gate_file(p)
    assert g.name == "tests-pass"
    assert g.model == "haiku"
    assert "${repo.path}" in g.text


def test_parse_gate_file_missing_gate_tag(tmp_path: Path):
    p = _write_gate(tmp_path, "bad", "no gate tag here\n")
    with pytest.raises(GateResultError, match="<gate>"):
        parse_gate_file(p)


def test_render_gate_prompt_substitutes(tmp_path: Path):
    p = _write_gate(tmp_path, "tests-pass", SIMPLE_GATE)
    g = parse_gate_file(p)
    ctx = GateContext(
        design_path="docs/superpowers/designs/2026-05-12-x.md",
        workflow="tdd",
        current_phase="green-api",
        phase_name="green-api",
        phase_repo="api",
        repo_name="api",
        repo_path="/abs/orc-penny/api",
    )
    prompt = render_gate_prompt(g, ctx)
    assert "/abs/orc-penny/api" in prompt
    assert "${repo.path}" not in prompt
    assert "<gate-context>" in prompt
    assert 'phase-repo="api"' in prompt or 'repo="api"' in prompt


def test_render_unscoped_omits_repo_in_context(tmp_path: Path):
    p = _write_gate(tmp_path, "tests-pass", SIMPLE_GATE)
    g = parse_gate_file(p)
    ctx = GateContext(
        design_path="docs/superpowers/designs/2026-05-12-x.md",
        workflow="tdd",
        current_phase="finish",
        phase_name="finish",
        phase_repo=None,
        repo_name=None,
        repo_path=None,
    )
    prompt = render_gate_prompt(g, ctx)
    # No <repo> element when phase is unscoped.
    assert '<repo ' not in prompt


def test_parse_gate_result_pass():
    text = textwrap.dedent("""\
        Some preamble.

        GATE_RESULT:
          status: pass
          gate: tests-pass
          repo: api
          message: "All tests passing"
          checks:
            - name: pytest
              status: pass
              detail: "412 passed"

        Trailing text.
    """)
    r = parse_gate_result(text)
    assert r["status"] == "pass"
    assert r["gate"] == "tests-pass"
    assert r["repo"] == "api"


def test_parse_gate_result_default_deny_no_block():
    with pytest.raises(GateResultError, match="not found"):
        parse_gate_result("nothing here\n")


def test_parse_gate_result_default_deny_unparseable():
    text = "GATE_RESULT:\n  status: : :\n"
    with pytest.raises(GateResultError, match="YAML|invalid"):
        parse_gate_result(text)


def test_parse_gate_result_rejects_unknown_status():
    text = textwrap.dedent("""\
        GATE_RESULT:
          status: maybe
          gate: x
          message: "huh"
    """)
    with pytest.raises(GateResultError, match="status"):
        parse_gate_result(text)


def test_builtin_gates_parse():
    plugin_root = Path(__file__).resolve().parents[1]
    for name in ("tests-fail", "tests-pass", "quality-pass", "approval", "design-complete"):
        path = plugin_root / "gates" / f"{name}.md"
        assert path.is_file(), f"missing {path}"
        g = parse_gate_file(path)
        assert g.name == name
