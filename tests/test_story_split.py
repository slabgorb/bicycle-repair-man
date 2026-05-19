"""Tests for Story model and `brm story split`."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from lib import story as _story

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
BRM = PLUGIN_ROOT / "scripts" / "brm"


def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(BRM), *args],
        cwd=cwd, capture_output=True, text=True,
    )


def _bootstrap_epic_with_plan(tmp_path, plan_body: str):
    _run("epic", "create", "demo", "--workflow", "tdd", "--repos", "brm", cwd=tmp_path)
    (tmp_path / ".brm" / "epics" / "demo" / "plan.md").write_text(plan_body)


def test_split_creates_story_files(tmp_path):
    plan = """# Plan

## Story: First

```yaml
slug: 01-first
acceptance:
  - "first AC"
```

Body 1.

## Story: Second

```yaml
slug: 02-second
acceptance: []
```

Body 2.
"""
    _bootstrap_epic_with_plan(tmp_path, plan)
    r = _run("story", "split", "demo", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    stories_dir = tmp_path / ".brm" / "epics" / "demo" / "stories"
    assert (stories_dir / "01-first.md").is_file()
    assert (stories_dir / "02-second.md").is_file()


def test_split_no_stories_in_plan_fails(tmp_path):
    _bootstrap_epic_with_plan(tmp_path, "# Plan\n\nNo stories here.\n")
    r = _run("story", "split", "demo", cwd=tmp_path)
    assert r.returncode != 0
    assert "## Story:" in r.stderr or "no stories" in r.stderr.lower()


def test_split_malformed_yaml_fails_with_line_number(tmp_path):
    plan = """# Plan

## Story: Bad

```yaml
slug: 01-bad
acceptance: [unclosed
```

Body.
"""
    _bootstrap_epic_with_plan(tmp_path, plan)
    r = _run("story", "split", "demo", cwd=tmp_path)
    assert r.returncode != 0
    assert "line" in r.stderr.lower()


def test_split_story_inherits_epic_workflow(tmp_path):
    plan = """# Plan

## Story: Inheriting

```yaml
slug: 01-inh
acceptance: []
```

Body.
"""
    _bootstrap_epic_with_plan(tmp_path, plan)
    _run("story", "split", "demo", cwd=tmp_path)
    from lib import story as _story
    s = _story.parse_story_text(
        (tmp_path / ".brm" / "epics" / "demo" / "stories" / "01-inh.md").read_text()
    )
    assert s.workflow == "tdd"  # inherited from epic
    assert s.repos == ["brm"]


def test_split_story_override_workflow_wins(tmp_path):
    plan = """# Plan

## Story: Override

```yaml
slug: 01-ovr
workflow: patch
repos: [brm]
acceptance: []
```

Body.
"""
    _bootstrap_epic_with_plan(tmp_path, plan)
    _run("story", "split", "demo", cwd=tmp_path)
    from lib import story as _story
    s = _story.parse_story_text(
        (tmp_path / ".brm" / "epics" / "demo" / "stories" / "01-ovr.md").read_text()
    )
    assert s.workflow == "patch"  # story override beats epic default


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


def test_resplit_preserves_phase_and_status(tmp_path):
    plan = """# Plan

## Story: One

```yaml
slug: 01-one
acceptance:
  - "AC text"
```

Body v1.
"""
    _bootstrap_epic_with_plan(tmp_path, plan)
    _run("story", "split", "demo", cwd=tmp_path)
    # Simulate work having occurred: phase advanced, status changed
    story_path = tmp_path / ".brm" / "epics" / "demo" / "stories" / "01-one.md"
    from lib import story as _story
    s = _story.parse_story_text(story_path.read_text())
    s.status = "in_progress"
    s.phase = "green"
    s.acceptance[0]["done"] = True
    story_path.write_text(_story.serialize_story(s))

    # Edit plan body and re-split
    new_plan = plan.replace("Body v1.", "Body v2 with new content.")
    (tmp_path / ".brm" / "epics" / "demo" / "plan.md").write_text(new_plan)
    r = _run("story", "split", "demo", cwd=tmp_path)
    assert r.returncode == 0, r.stderr

    s2 = _story.parse_story_text(story_path.read_text())
    assert s2.status == "in_progress"   # preserved
    assert s2.phase == "green"           # preserved
    assert s2.acceptance[0]["done"] is True  # preserved
    assert "Body v2 with new content" in s2.body  # body replaced


def test_resplit_adds_new_ac_unchecked(tmp_path):
    plan = """# Plan

## Story: One

```yaml
slug: 01-one
acceptance:
  - "first"
```

Body.
"""
    _bootstrap_epic_with_plan(tmp_path, plan)
    _run("story", "split", "demo", cwd=tmp_path)
    story_path = tmp_path / ".brm" / "epics" / "demo" / "stories" / "01-one.md"
    from lib import story as _story
    s = _story.parse_story_text(story_path.read_text())
    s.acceptance[0]["done"] = True
    story_path.write_text(_story.serialize_story(s))

    new_plan = plan.replace(
        "  - \"first\"",
        "  - \"first\"\n  - \"second\"",
    )
    (tmp_path / ".brm" / "epics" / "demo" / "plan.md").write_text(new_plan)
    _run("story", "split", "demo", cwd=tmp_path)

    s2 = _story.parse_story_text(story_path.read_text())
    assert len(s2.acceptance) == 2
    assert s2.acceptance[0]["text"] == "first" and s2.acceptance[0]["done"] is True
    assert s2.acceptance[1]["text"] == "second" and s2.acceptance[1]["done"] is False


def test_slug_rename_without_force_warns_and_skips(tmp_path):
    plan = """# Plan

## Story: One

```yaml
slug: 01-one
acceptance: []
```

Body.
"""
    _bootstrap_epic_with_plan(tmp_path, plan)
    _run("story", "split", "demo", cwd=tmp_path)
    # Rename slug in plan
    renamed = plan.replace("slug: 01-one", "slug: 01-renamed")
    (tmp_path / ".brm" / "epics" / "demo" / "plan.md").write_text(renamed)
    r = _run("story", "split", "demo", cwd=tmp_path)
    # Without --force, the new slug creates a new file; the old becomes orphan
    assert (tmp_path / ".brm" / "epics" / "demo" / "stories" / "01-one.md").is_file()
    assert (tmp_path / ".brm" / "epics" / "demo" / "stories" / "01-renamed.md").is_file()
    assert "orphan" in r.stderr.lower() or "no longer" in r.stderr.lower()
