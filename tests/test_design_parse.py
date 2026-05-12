"""Unit tests for lib/design.py parse + dataclasses."""
from __future__ import annotations

import datetime as _dt
import textwrap

import pytest

from lib.design import (
    Design,
    DesignSchemaError,
    Phase,
    parse_design_text,
    serialize_design,
    advance_phase,
    record_gate_pass,
    record_gate_fail,
    start_phase,
    block_design,
    unblock_design,
    mark_complete,
    mark_abandoned,
    DesignTransitionError,
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


def _fresh_planned_design():
    text = textwrap.dedent("""\
        ---
        design: 2026-05-12-x
        created: 2026-05-12T10:00:00-04:00
        workflow: tdd
        repos: [api]
        status: planned
        current_phase: red-api
        phases:
          - {name: red-api, repo: api, status: planned, started: null, finished: null, handoff: null, gate_result: null}
          - {name: green-api, repo: api, status: planned, started: null, finished: null, handoff: null, gate_result: null}
        history: []
        ---

        body
    """)
    return parse_design_text(text)


def test_serialize_round_trip():
    d = parse_design_text(VALID_DESIGN)
    text = serialize_design(d)
    d2 = parse_design_text(text)
    assert d2 == d


def test_start_phase_marks_in_progress_and_records_history():
    d = _fresh_planned_design()
    d = start_phase(d, "red-api", actor="tea", at="2026-05-12T10:01:00-04:00")
    assert d.phase("red-api").status == "in-progress"
    assert d.phase("red-api").started == "2026-05-12T10:01:00-04:00"
    assert d.status == "in-progress"
    assert d.history[-1] == {
        "at": "2026-05-12T10:01:00-04:00",
        "event": "phase-start",
        "phase": "red-api",
        "actor": "tea",
    }


def test_record_gate_pass_then_advance():
    d = _fresh_planned_design()
    d = start_phase(d, "red-api", actor="tea", at="2026-05-12T10:01:00-04:00")
    d = record_gate_pass(d, gate="tests-fail", at="2026-05-12T10:10:00-04:00", actor="tea")
    assert d.phase("red-api").gate_result == "pass"
    d = advance_phase(d, to="green-api", at="2026-05-12T10:11:00-04:00")
    assert d.current_phase == "green-api"
    assert d.phase("red-api").status == "complete"
    assert d.phase("red-api").finished == "2026-05-12T10:11:00-04:00"
    assert d.phase("green-api").status == "in-progress"


def test_advance_without_gate_pass_rejected():
    d = _fresh_planned_design()
    d = start_phase(d, "red-api", actor="tea", at="2026-05-12T10:01:00-04:00")
    with pytest.raises(DesignTransitionError, match="gate"):
        advance_phase(d, to="green-api", at="2026-05-12T10:11:00-04:00")


def test_advance_force_records_phase_skip():
    d = _fresh_planned_design()
    d = start_phase(d, "red-api", actor="tea", at="2026-05-12T10:01:00-04:00")
    d = advance_phase(d, to="green-api", at="2026-05-12T10:11:00-04:00", force=True)
    assert any(h["event"] == "phase-skip" for h in d.history)


def test_record_gate_fail_does_not_advance():
    d = _fresh_planned_design()
    d = start_phase(d, "red-api", actor="tea", at="2026-05-12T10:01:00-04:00")
    d = record_gate_fail(d, gate="tests-fail", at="2026-05-12T10:10:00-04:00", actor="tea")
    assert d.phase("red-api").gate_result == "fail"
    assert d.current_phase == "red-api"


def test_block_unblock_round_trip():
    d = _fresh_planned_design()
    d = start_phase(d, "red-api", actor="tea", at="2026-05-12T10:01:00-04:00")
    d = block_design(d, reason="waiting on external API spec", at="2026-05-12T10:30:00-04:00")
    assert d.status == "blocked"
    d = unblock_design(d, at="2026-05-12T11:00:00-04:00")
    assert d.status == "in-progress"


def test_mark_complete_requires_all_phases_complete():
    d = _fresh_planned_design()
    with pytest.raises(DesignTransitionError, match="not.*complete"):
        mark_complete(d, at="2026-05-12T12:00:00-04:00")


def test_mark_abandoned_terminal():
    d = _fresh_planned_design()
    d = mark_abandoned(d, reason="superseded", at="2026-05-12T12:00:00-04:00")
    assert d.status == "abandoned"


def test_advance_to_self_rejected():
    d = _fresh_planned_design()
    d = start_phase(d, "red-api", actor="tea", at="2026-05-12T10:01:00-04:00")
    d = record_gate_pass(d, gate="tests-fail", at="2026-05-12T10:10:00-04:00", actor="tea")
    with pytest.raises(DesignTransitionError, match="current phase"):
        advance_phase(d, to="red-api", at="2026-05-12T10:11:00-04:00")


def test_advance_from_planned_phase_rejected_even_with_force():
    d = _fresh_planned_design()
    # current_phase is red-api but start_phase was never called → status is "planned"
    with pytest.raises(DesignTransitionError, match="not in-progress"):
        advance_phase(d, to="green-api", at="2026-05-12T10:11:00-04:00", force=True)
