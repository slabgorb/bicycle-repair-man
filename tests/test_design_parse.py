"""Unit tests for lib/design.py parse + dataclasses."""
from __future__ import annotations

import textwrap

import pytest

from lib.design import (
    Design,
    DesignSchemaError,
    Phase,
    parse_design_text,
)


VALID_DESIGN = textwrap.dedent("""\
    ---
    design: 2026-05-12-cache-fix
    created: 2026-05-12T14:22:00-04:00
    workflow: tdd
    repos: [api, ui]
    description: Fix stale cache bug.
    status: in-progress
    current_phase: green-api
    phases:
      - name: red-api
        repo: api
        status: complete
        started: 2026-05-12T14:25:11-04:00
        finished: 2026-05-12T14:42:03-04:00
        handoff: "#handoffs/red-api"
        gate_result: pass
      - name: green-api
        repo: api
        status: in-progress
        started: 2026-05-12T14:59:00-04:00
        finished: null
        handoff: null
        gate_result: null
    history:
      - at: 2026-05-12T14:25:11-04:00
        event: phase-start
        phase: red-api
        actor: tea
    ---

    # Body

    ## Handoffs

    ### red-api {#handoffs/red-api}
    <handoff from="red-api" to="green-api" repo="api" agent="tea" at="2026-05-12T14:42:03-04:00">
    Summary: 3 failing tests added.
    </handoff>
""")


def test_parse_happy_path():
    d = parse_design_text(VALID_DESIGN)
    assert d.design == "2026-05-12-cache-fix"
    assert d.workflow == "tdd"
    assert d.repos == ["api", "ui"]
    assert d.status == "in-progress"
    assert d.current_phase == "green-api"
    assert len(d.phases) == 2
    assert d.phases[0].name == "red-api"
    assert d.phases[0].status == "complete"
    assert d.phases[0].gate_result == "pass"
    assert d.phases[1].status == "in-progress"
    assert d.phases[1].finished is None


def test_parse_preserves_body():
    d = parse_design_text(VALID_DESIGN)
    assert "## Handoffs" in d.body
    assert "{#handoffs/red-api}" in d.body


def test_parse_missing_frontmatter_delimiter():
    text = "design: foo\nstatus: in-progress\n"
    with pytest.raises(DesignSchemaError, match="frontmatter"):
        parse_design_text(text)


def test_parse_unclosed_frontmatter():
    text = "---\ndesign: foo\nstatus: in-progress\n"
    with pytest.raises(DesignSchemaError, match="frontmatter"):
        parse_design_text(text)


def test_parse_malformed_yaml():
    text = "---\n  bad: : :\n---\n\nbody\n"
    with pytest.raises(DesignSchemaError, match="YAML"):
        parse_design_text(text)


def test_parse_missing_required_field():
    text = textwrap.dedent("""\
        ---
        design: foo
        workflow: tdd
        repos: [api]
        status: in-progress
        ---

        body
    """)
    with pytest.raises(DesignSchemaError, match="created"):
        parse_design_text(text)


def test_parse_invalid_status():
    text = textwrap.dedent("""\
        ---
        design: foo
        created: 2026-05-12T14:22:00-04:00
        workflow: tdd
        repos: [api]
        status: garbage
        current_phase: red-api
        phases:
          - {name: red-api, repo: api, status: planned, started: null, finished: null, handoff: null, gate_result: null}
        history: []
        ---

        body
    """)
    with pytest.raises(DesignSchemaError, match="status"):
        parse_design_text(text)


def test_parse_empty_repos_rejected():
    text = textwrap.dedent("""\
        ---
        design: foo
        created: 2026-05-12T14:22:00-04:00
        workflow: tdd
        repos: []
        status: planned
        current_phase: red-api
        phases:
          - {name: red-api, repo: api, status: planned, started: null, finished: null, handoff: null, gate_result: null}
        history: []
        ---

        body
    """)
    with pytest.raises(DesignSchemaError, match="repos"):
        parse_design_text(text)


def test_parse_phase_repo_xor_repos():
    text = textwrap.dedent("""\
        ---
        design: foo
        created: 2026-05-12T14:22:00-04:00
        workflow: tdd
        repos: [api, ui]
        status: planned
        current_phase: review
        phases:
          - {name: review, repo: api, repos: [api, ui], status: planned, started: null, finished: null, handoff: null, gate_result: null}
        history: []
        ---

        body
    """)
    with pytest.raises(DesignSchemaError, match="repo.*repos"):
        parse_design_text(text)


def test_parse_phases_null_rejected():
    text = textwrap.dedent("""\
        ---
        design: foo
        created: 2026-05-12T14:22:00-04:00
        workflow: tdd
        repos: [api]
        status: planned
        current_phase: red-api
        phases: null
        history: []
        ---

        body
    """)
    with pytest.raises(DesignSchemaError, match="phases"):
        parse_design_text(text)
