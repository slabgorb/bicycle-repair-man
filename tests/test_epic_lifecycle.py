"""Tests for the Epic data model and lifecycle."""
from __future__ import annotations

import pytest

from lib import epic as _epic

EPIC_TEXT = """---
schema: brm-epic/0.4
slug: 2026-05-19-test-epic
title: Test epic
status: draft
workflow: tdd
repos: [brm]
created: 2026-05-19
---

# Test epic

Body content.
"""


def test_parse_minimal_epic():
    e = _epic.parse_epic_text(EPIC_TEXT)
    assert e.slug == "2026-05-19-test-epic"
    assert e.title == "Test epic"
    assert e.status == "draft"
    assert e.workflow == "tdd"
    assert e.repos == ["brm"]
    assert "Body content." in e.body


def test_parse_missing_required_field_raises():
    bad = EPIC_TEXT.replace("workflow: tdd\n", "")
    with pytest.raises(_epic.EpicSchemaError, match="workflow"):
        _epic.parse_epic_text(bad)


def test_parse_invalid_status_raises():
    bad = EPIC_TEXT.replace("status: draft", "status: nonsense")
    with pytest.raises(_epic.EpicSchemaError, match="status"):
        _epic.parse_epic_text(bad)


def test_serialize_roundtrip():
    e = _epic.parse_epic_text(EPIC_TEXT)
    out = _epic.serialize_epic(e)
    e2 = _epic.parse_epic_text(out)
    assert e2.slug == e.slug
    assert e2.title == e.title
    assert e2.status == e.status
    assert e2.workflow == e.workflow
    assert e2.repos == e.repos
    assert "Body content." in e2.body


def test_spec_approval_optional():
    e = _epic.parse_epic_text(EPIC_TEXT)
    assert e.spec_approval is None  # default


def test_spec_approval_parsed_when_present():
    with_approval = EPIC_TEXT.replace(
        "created: 2026-05-19\n",
        "created: 2026-05-19\nspec_approval:\n  required: true\n  approved_at: 2026-05-19T14:22:00Z\n  approver: keith\n",
    )
    e = _epic.parse_epic_text(with_approval)
    assert e.spec_approval is not None
    assert e.spec_approval.required is True
    assert e.spec_approval.approved_at == "2026-05-19T14:22:00Z"
    assert e.spec_approval.approver == "keith"


def test_spec_approval_normalizes_offset_datetime():
    with_offset = EPIC_TEXT.replace(
        "created: 2026-05-19\n",
        "created: 2026-05-19\nspec_approval:\n  required: true\n  approved_at: 2026-05-19T16:22:00+02:00\n  approver: keith\n",
    )
    e = _epic.parse_epic_text(with_offset)
    assert e.spec_approval is not None
    assert e.spec_approval.approved_at == "2026-05-19T14:22:00Z"


# ---------------------------------------------------------------------------
# CLI tests — brm epic create
# ---------------------------------------------------------------------------

import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
BRM = PLUGIN_ROOT / "scripts" / "brm"


def _run_brm(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(BRM), *args],
        cwd=cwd, capture_output=True, text=True,
    )


def test_brm_epic_create_makes_folder_and_file(tmp_path):
    r = _run_brm("epic", "create", "demo", "--workflow", "tdd", "--repos", "brm", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    epic_dir = tmp_path / ".brm" / "epics" / "demo"
    assert epic_dir.is_dir()
    assert (epic_dir / "epic.md").is_file()
    assert (epic_dir / "stories").is_dir()


def test_brm_epic_create_writes_valid_frontmatter(tmp_path):
    _run_brm("epic", "create", "demo", "--workflow", "tdd", "--repos", "brm", cwd=tmp_path)
    from lib import epic as _epic
    text = (tmp_path / ".brm" / "epics" / "demo" / "epic.md").read_text()
    e = _epic.parse_epic_text(text)
    assert e.slug == "demo"
    assert e.status == "draft"
    assert e.workflow == "tdd"
    assert e.repos == ["brm"]


def test_brm_epic_create_refuses_duplicate(tmp_path):
    _run_brm("epic", "create", "demo", "--workflow", "tdd", "--repos", "brm", cwd=tmp_path)
    r = _run_brm("epic", "create", "demo", "--workflow", "tdd", "--repos", "brm", cwd=tmp_path)
    assert r.returncode != 0
    assert "exists" in (r.stdout + r.stderr).lower()
