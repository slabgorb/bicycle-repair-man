"""Tests for Story model and `brm story split`."""
from __future__ import annotations

import pytest

from lib import story as _story


STORY_TEXT = """---
schema: brm-story/0.4
slug: 01-foo
title: Foo story
epic: alpha
workflow: tdd
repos: [brm]
status: draft
phase: null
phase_history: []
acceptance:
  - { done: false, text: "first AC" }
  - { done: false, text: "second AC" }
---

# Foo story

Body content from the plan slice.
"""


def test_parse_story():
    s = _story.parse_story_text(STORY_TEXT)
    assert s.slug == "01-foo"
    assert s.title == "Foo story"
    assert s.epic == "alpha"
    assert s.workflow == "tdd"
    assert s.repos == ["brm"]
    assert s.status == "draft"
    assert s.phase is None
    assert s.acceptance == [
        {"done": False, "text": "first AC"},
        {"done": False, "text": "second AC"},
    ]


def test_parse_invalid_status_raises():
    bad = STORY_TEXT.replace("status: draft", "status: nonsense")
    with pytest.raises(_story.StorySchemaError, match="status"):
        _story.parse_story_text(bad)


def test_serialize_roundtrip():
    s = _story.parse_story_text(STORY_TEXT)
    out = _story.serialize_story(s)
    s2 = _story.parse_story_text(out)
    assert s2.slug == s.slug
    assert s2.status == s.status
    assert s2.acceptance == s.acceptance


def test_phase_history_preserved():
    text = STORY_TEXT.replace(
        "phase_history: []",
        "phase_history:\n"
        "  - { phase: red, entered: 2026-05-19T15:10:00Z, exited: 2026-05-19T16:42:00Z, gate_result: pass }",
    ).replace("phase: null", "phase: green").replace("status: draft", "status: in_progress")
    s = _story.parse_story_text(text)
    assert len(s.phase_history) == 1
    assert s.phase_history[0]["phase"] == "red"
    out = _story.serialize_story(s)
    s2 = _story.parse_story_text(out)
    assert s2.phase_history == s.phase_history
