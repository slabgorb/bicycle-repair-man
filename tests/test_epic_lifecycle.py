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
