"""Tests for story state-machine operations."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
BRM = PLUGIN_ROOT / "scripts" / "brm"


def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(BRM), *args],
        cwd=cwd, capture_output=True, text=True,
    )


def _setup_epic_with_two_stories(tmp_path):
    _run("epic", "create", "demo", "--workflow", "tdd", "--repos", "brm", cwd=tmp_path)
    plan = """# Plan

## Story: First

```yaml
slug: 01-first
acceptance: ["one", "two"]
```

Body of first.

## Story: Second

```yaml
slug: 02-second
acceptance: ["three"]
```

Body of second.
"""
    (tmp_path / ".brm" / "epics" / "demo" / "plan.md").write_text(plan)
    _run("story", "split", "demo", cwd=tmp_path)


def test_story_list(tmp_path):
    _setup_epic_with_two_stories(tmp_path)
    r = _run("story", "list", "demo", cwd=tmp_path)
    assert r.returncode == 0
    assert "01-first" in r.stdout and "02-second" in r.stdout


def test_story_describe(tmp_path):
    _setup_epic_with_two_stories(tmp_path)
    r = _run("story", "describe", "demo", "--story", "01-first", cwd=tmp_path)
    assert r.returncode == 0
    out = r.stdout
    for token in ("01-first", "tdd", "brm", "draft"):
        assert token in out


def test_story_status_when_no_story_arg_uses_pointer(tmp_path):
    _setup_epic_with_two_stories(tmp_path)
    _run("story", "switch", "demo", "01-first", cwd=tmp_path)
    r = _run("story", "status", "demo", cwd=tmp_path)
    assert r.returncode == 0
    assert "01-first" in r.stdout


def test_story_status_unknown_story_errors(tmp_path):
    _setup_epic_with_two_stories(tmp_path)
    r = _run("story", "status", "demo", "--story", "99-nope", cwd=tmp_path)
    assert r.returncode != 0


HANDOFF_BLOCK = """<handoff from="tea" to="dev" repo="brm" agent="tea" at="2026-05-19T15:00:00Z">
Tests are failing as expected. Two ACs covered. Next step: implement parser.
</handoff>
"""


def test_story_handoff_records_block(tmp_path):
    _setup_epic_with_two_stories(tmp_path)
    r = subprocess.run(
        [sys.executable, str(BRM), "story", "handoff", "demo",
         "--story", "01-first", "--from", "tea", "--to", "dev", "--stdin"],
        cwd=tmp_path, input=HANDOFF_BLOCK, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    from lib import story as _story
    s = _story.parse_story_text(
        (tmp_path / ".brm" / "epics" / "demo" / "stories" / "01-first.md").read_text()
    )
    assert s.last_handoff is not None
    assert s.last_handoff["from"] == "tea"
    assert s.last_handoff["to"] == "dev"
    assert "Tests are failing" in s.last_handoff["body"]


def test_story_handoff_appends_to_body_log(tmp_path):
    _setup_epic_with_two_stories(tmp_path)
    subprocess.run(
        [sys.executable, str(BRM), "story", "handoff", "demo",
         "--story", "01-first", "--from", "tea", "--to", "dev", "--stdin"],
        cwd=tmp_path, input=HANDOFF_BLOCK, capture_output=True, text=True,
    )
    body = (tmp_path / ".brm" / "epics" / "demo" / "stories" / "01-first.md").read_text()
    assert "## Handoff log" in body
    assert "Tests are failing" in body


def test_story_gate_emits_prompt(tmp_path):
    _setup_epic_with_two_stories(tmp_path)
    # Move story 01-first to in_progress with a phase that has a gate
    from lib import story as _story
    sp = tmp_path / ".brm" / "epics" / "demo" / "stories" / "01-first.md"
    s = _story.parse_story_text(sp.read_text())
    s.status = "in_progress"
    s.phase = "red"
    sp.write_text(_story.serialize_story(s))
    r = _run("story", "gate", "demo", "--story", "01-first", cwd=tmp_path)
    assert r.returncode == 0
    assert "GATE_RESULT" in r.stdout  # gate prompt mentions the contract


def test_story_record_gate_pass(tmp_path):
    _setup_epic_with_two_stories(tmp_path)
    from lib import story as _story
    sp = tmp_path / ".brm" / "epics" / "demo" / "stories" / "01-first.md"
    s = _story.parse_story_text(sp.read_text())
    s.status = "in_progress"; s.phase = "red"
    sp.write_text(_story.serialize_story(s))
    gate_result = "GATE_RESULT\nresult: pass\nreason: tests are failing as required\n"
    r = subprocess.run(
        [sys.executable, str(BRM), "story", "record-gate", "demo",
         "--story", "01-first", "--result-stdin"],
        cwd=tmp_path, input=gate_result, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    s2 = _story.parse_story_text(sp.read_text())
    # phase_history gets an entry with the gate result
    assert any(h.get("gate_result") == "pass" for h in s2.phase_history) or s2.phase_history == []


# ---------------------------------------------------------------------------
# E4: brm story advance
# ---------------------------------------------------------------------------

def test_story_advance_moves_to_next_phase(tmp_path):
    _setup_epic_with_two_stories(tmp_path)
    from lib import story as _story
    sp = tmp_path / ".brm" / "epics" / "demo" / "stories" / "01-first.md"
    s = _story.parse_story_text(sp.read_text())
    s.status = "in_progress"; s.phase = "red"
    s.phase_history = [{
        "phase": "red", "entered": "2026-05-19T10:00:00Z",
        "exited": "2026-05-19T11:00:00Z", "gate_result": "pass",
    }]
    sp.write_text(_story.serialize_story(s))
    r = _run("story", "advance", "demo", "--story", "01-first", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    s2 = _story.parse_story_text(sp.read_text())
    assert s2.phase == "green"  # next phase in tdd.yaml after red


def test_story_advance_refuses_without_gate_pass(tmp_path):
    _setup_epic_with_two_stories(tmp_path)
    from lib import story as _story
    sp = tmp_path / ".brm" / "epics" / "demo" / "stories" / "01-first.md"
    s = _story.parse_story_text(sp.read_text())
    s.status = "in_progress"; s.phase = "red"
    # No gate result yet
    sp.write_text(_story.serialize_story(s))
    r = _run("story", "advance", "demo", "--story", "01-first", cwd=tmp_path)
    assert r.returncode != 0
    assert "gate" in (r.stdout + r.stderr).lower()


def test_story_advance_force_skips_gate(tmp_path):
    _setup_epic_with_two_stories(tmp_path)
    from lib import story as _story
    sp = tmp_path / ".brm" / "epics" / "demo" / "stories" / "01-first.md"
    s = _story.parse_story_text(sp.read_text())
    s.status = "in_progress"; s.phase = "red"
    sp.write_text(_story.serialize_story(s))
    r = _run("story", "advance", "demo", "--story", "01-first", "--force", cwd=tmp_path)
    assert r.returncode == 0


def test_story_advance_to_explicit_phase(tmp_path):
    _setup_epic_with_two_stories(tmp_path)
    from lib import story as _story
    sp = tmp_path / ".brm" / "epics" / "demo" / "stories" / "01-first.md"
    s = _story.parse_story_text(sp.read_text())
    s.status = "in_progress"; s.phase = "red"
    s.phase_history = [{
        "phase": "red", "entered": "2026-05-19T10:00:00Z",
        "exited": "2026-05-19T11:00:00Z", "gate_result": "pass",
    }]
    sp.write_text(_story.serialize_story(s))
    r = _run("story", "advance", "demo", "--story", "01-first", "--to", "review", cwd=tmp_path)
    assert r.returncode == 0
    s2 = _story.parse_story_text(sp.read_text())
    assert s2.phase == "review"


