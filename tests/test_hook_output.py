"""Subprocess golden-output tests for the UserPromptSubmit hook."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_SCRIPT = REPO_ROOT / "hooks" / "on-user-prompt-submit.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "sidecars"


def _run_hook(
    prompt: str,
    *,
    home: Path,
    project_root: Path | None,
) -> dict:
    env = {
        **os.environ,
        "BRM_HOME": str(home),
    }
    if project_root is not None:
        env["BRM_PROJECT_ROOT"] = str(project_root)
    else:
        env.pop("BRM_PROJECT_ROOT", None)
    event = json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": prompt})
    proc = subprocess.run(
        ["python3", str(HOOK_SCRIPT)],
        input=event,
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout or "{}")


def _additional(out: dict) -> str:
    return out.get("hookSpecificOutput", {}).get("additionalContext", "")


# --- No-match cases ------------------------------------------------------

def test_no_command_emits_empty(tmp_path: Path) -> None:
    out = _run_hook("hello there", home=tmp_path, project_root=tmp_path)
    assert out == {}


def test_unknown_command_emits_empty(tmp_path: Path) -> None:
    out = _run_hook("/foo bar", home=tmp_path, project_root=tmp_path)
    assert out == {}


def test_longer_prefix_no_match(tmp_path: Path) -> None:
    out = _run_hook("/reviewer-fresh hi", home=tmp_path, project_root=tmp_path)
    assert out == {}


def test_case_sensitive_no_match(tmp_path: Path) -> None:
    out = _run_hook("/Reviewer hi", home=tmp_path, project_root=tmp_path)
    assert out == {}


# --- Match + present layer cases ----------------------------------------

def test_match_with_both_layers(tmp_path: Path) -> None:
    out = _run_hook(
        "/reviewer look at the cache change",
        home=FIXTURES / "global",
        project_root=FIXTURES / "project",
    )
    ctx = _additional(out)
    assert '<brm-sidecar role="reviewer">' in ctx
    assert '<layer scope="global"' in ctx
    assert '<layer scope="project"' in ctx
    assert "Always read tests before implementation" in ctx
    assert "Caching layer reviews must include eviction proofs" in ctx


def test_match_namespaced_command(tmp_path: Path) -> None:
    out = _run_hook(
        "/brm:reviewer look",
        home=FIXTURES / "global",
        project_root=FIXTURES / "project",
    )
    ctx = _additional(out)
    assert '<brm-sidecar role="reviewer">' in ctx


def test_match_global_only(tmp_path: Path) -> None:
    out = _run_hook(
        "/reviewer hi",
        home=FIXTURES / "global",
        project_root=tmp_path,  # no .brm here
    )
    ctx = _additional(out)
    assert '<layer scope="global"' in ctx
    assert '<layer scope="project"' not in ctx


def test_match_project_only(tmp_path: Path) -> None:
    out = _run_hook(
        "/reviewer hi",
        home=tmp_path,  # no global file
        project_root=FIXTURES / "project",
    )
    ctx = _additional(out)
    assert '<layer scope="project"' in ctx
    assert '<layer scope="global"' not in ctx


def test_match_neither_layer_emits_empty(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".brm").mkdir()  # marker but no sidecar
    out = _run_hook("/reviewer hi", home=home, project_root=proj)
    assert out == {}


# --- Robustness ----------------------------------------------------------

def test_malformed_stdin_exits_zero_empty(tmp_path: Path) -> None:
    env = {**os.environ, "BRM_HOME": str(tmp_path)}
    proc = subprocess.run(
        ["python3", str(HOOK_SCRIPT)],
        input="not json at all",
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() in ("{}", '{"hookSpecificOutput": {}}')
