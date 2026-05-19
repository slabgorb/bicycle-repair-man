"""Tests for v0.4 hook output: <brm-epic> and <brm-story> blocks."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
HOOK = PLUGIN_ROOT / "hooks" / "on-user-prompt-submit.py"


def _run_hook(prompt: str, cwd: Path):
    payload = json.dumps({"prompt": prompt})
    return subprocess.run(
        [sys.executable, str(HOOK)],
        cwd=cwd, input=payload, capture_output=True, text=True,
        env={"CLAUDE_PROJECT_DIR": str(cwd), "PATH": ""},
    )


def _bootstrap_active_epic(cwd):
    """Create an active epic with a current_story under cwd/.brm/epics/."""
    BRM = PLUGIN_ROOT / "scripts" / "brm"
    subprocess.run([sys.executable, str(BRM), "epic", "create", "demo",
                    "--workflow", "tdd", "--repos", "brm"], cwd=cwd, check=True)
    plan = """# Plan

## Story: First

```yaml
slug: 01-first
acceptance: ["AC1"]
```

Body.
"""
    (cwd / ".brm" / "epics" / "demo" / "plan.md").write_text(plan)
    subprocess.run([sys.executable, str(BRM), "story", "split", "demo"],
                   cwd=cwd, check=True)
    subprocess.run([sys.executable, str(BRM), "epic", "activate", "demo"],
                   cwd=cwd, check=True)
    subprocess.run([sys.executable, str(BRM), "story", "switch", "demo", "01-first"],
                   cwd=cwd, check=True)


def test_hook_emits_brm_epic_on_role_activation(tmp_path):
    _bootstrap_active_epic(tmp_path)
    r = _run_hook("/pm look at this", cwd=tmp_path)
    assert r.returncode == 0
    out = json.loads(r.stdout)
    ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
    assert "<brm-epic>" in ctx
    assert "<slug>demo</slug>" in ctx
    assert "<status>active</status>" in ctx


def test_hook_emits_brm_story_with_pointer(tmp_path):
    _bootstrap_active_epic(tmp_path)
    r = _run_hook("/dev work on this", cwd=tmp_path)
    out = json.loads(r.stdout)
    ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
    assert "<brm-story>" in ctx
    assert "<slug>01-first</slug>" in ctx


def test_hook_no_epic_skips_block(tmp_path):
    # cwd has no .brm/epics/
    r = _run_hook("/pm hello", cwd=tmp_path)
    out = json.loads(r.stdout)
    ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "") or ""
    assert "<brm-epic>" not in ctx


def test_hook_non_match_still_zero_io(tmp_path):
    """v0.1.0 invariant: non-role prompts must not touch the filesystem."""
    _bootstrap_active_epic(tmp_path)
    r = _run_hook("just a regular message, no slash command", cwd=tmp_path)
    out = json.loads(r.stdout)
    assert out == {} or out.get("hookSpecificOutput", {}).get("additionalContext", "") == ""


def test_cli_story_override_does_not_change_pointer(tmp_path):
    _bootstrap_active_epic(tmp_path)
    # Add a second story by adding to the plan and re-splitting
    plan = (tmp_path / ".brm" / "epics" / "demo" / "plan.md").read_text()
    plan += "\n## Story: Second\n\n```yaml\nslug: 02-second\nacceptance: []\n```\n\nBody2.\n"
    (tmp_path / ".brm" / "epics" / "demo" / "plan.md").write_text(plan)
    BRM = PLUGIN_ROOT / "scripts" / "brm"
    subprocess.run([sys.executable, str(BRM), "story", "split", "demo"], cwd=tmp_path)
    # Describe with --story 02-second; pointer should remain 01-first
    subprocess.run([sys.executable, str(BRM), "story", "describe", "demo",
                    "--story", "02-second"], cwd=tmp_path)
    from lib import epic as _epic_mod
    e = _epic_mod.parse_epic_text(
        (tmp_path / ".brm" / "epics" / "demo" / "epic.md").read_text()
    )
    assert e.current_story == "01-first"
