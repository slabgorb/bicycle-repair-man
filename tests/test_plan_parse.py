"""Tests for plan.md parsing (## Story: markers + YAML fences)."""
from __future__ import annotations

from pathlib import Path

import pytest

from lib import plan as _plan


PLAN_TEXT = """# Implementation plan — demo

Preamble paragraph that is plan-level, not story-level.

## Story: First story

```yaml
slug: 01-first
workflow: tdd
repos: [brm]
acceptance:
  - "first AC"
  - "second AC"
```

Body of the first story. Free-form markdown.

## Story: Second story

```yaml
slug: 02-second
acceptance:
  - "another AC"
```

Body of the second story.
"""


def test_parse_returns_two_stories():
    plan = _plan.parse_plan_text(PLAN_TEXT)
    assert len(plan.stories) == 2
    assert plan.stories[0].slug == "01-first"
    assert plan.stories[1].slug == "02-second"


def test_parse_preserves_titles():
    plan = _plan.parse_plan_text(PLAN_TEXT)
    assert plan.stories[0].title == "First story"
    assert plan.stories[1].title == "Second story"


def test_parse_extracts_yaml_fields():
    plan = _plan.parse_plan_text(PLAN_TEXT)
    s = plan.stories[0]
    assert s.workflow == "tdd"
    assert s.repos == ["brm"]
    assert s.acceptance == ["first AC", "second AC"]


def test_parse_preserves_body():
    plan = _plan.parse_plan_text(PLAN_TEXT)
    body = plan.stories[0].body
    assert "Body of the first story" in body
    assert "## Story:" not in body  # body stops before the next marker


def test_parse_preserves_preamble():
    plan = _plan.parse_plan_text(PLAN_TEXT)
    assert "Preamble paragraph" in plan.preamble


def test_parse_no_stories_returns_empty_list():
    text = "# Plan\n\nJust preamble, no stories.\n"
    plan = _plan.parse_plan_text(text)
    assert plan.stories == []
    assert "Just preamble" in plan.preamble


def test_parse_missing_yaml_fence_raises():
    bad = """# Plan

## Story: No fence

This story is missing its YAML fence.
"""
    with pytest.raises(_plan.PlanParseError, match="YAML fence"):
        _plan.parse_plan_text(bad)


def test_parse_missing_slug_in_fence_raises():
    bad = """# Plan

## Story: Bad

```yaml
workflow: tdd
```

Body.
"""
    with pytest.raises(_plan.PlanParseError, match="slug"):
        _plan.parse_plan_text(bad)


def test_parse_duplicate_slugs_raises():
    dup = PLAN_TEXT.replace("02-second", "01-first")
    with pytest.raises(_plan.PlanParseError, match="duplicate"):
        _plan.parse_plan_text(dup)


def test_parse_invalid_slug_format_raises():
    bad = PLAN_TEXT.replace("slug: 01-first", "slug: 01_First!")
    with pytest.raises(_plan.PlanParseError, match="slug"):
        _plan.parse_plan_text(bad)


def test_validate_plan_against_orchestrator_passes_clean(tmp_path):
    plan = _plan.parse_plan_text(PLAN_TEXT)
    # Simulate orchestrator with repo "brm" present
    known_repos = {"brm"}
    known_workflows = {"tdd"}
    errors = _plan.validate_plan(plan, known_repos=known_repos, known_workflows=known_workflows)
    assert errors == []


def test_validate_plan_flags_unknown_workflow():
    text = PLAN_TEXT.replace("workflow: tdd", "workflow: doesnotexist")
    plan = _plan.parse_plan_text(text)
    errors = _plan.validate_plan(plan, known_repos={"brm"}, known_workflows={"tdd"})
    assert any("doesnotexist" in e for e in errors)


def test_validate_plan_flags_unknown_repo():
    text = PLAN_TEXT.replace("repos: [brm]", "repos: [phantom]")
    plan = _plan.parse_plan_text(text)
    errors = _plan.validate_plan(plan, known_repos={"brm"}, known_workflows={"tdd"})
    assert any("phantom" in e for e in errors)
