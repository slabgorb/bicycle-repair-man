"""Subprocess tests for scripts/brm-design."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "brm-design"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "designs" / "orchestrator"


def _run(args, *, cwd, env=None, input_text=None):
    env = {**os.environ, **(env or {})}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd),
        env=env,
        input=input_text,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def orch(tmp_path: Path) -> Path:
    target = tmp_path / "orch"
    shutil.copytree(FIXTURE, target)
    return target


def test_script_exists_and_executable():
    assert SCRIPT.is_file()
    assert os.access(SCRIPT, os.X_OK), "scripts/brm-design must be executable"


def test_help_exits_zero(orch: Path):
    r = _run(["--help"], cwd=orch)
    assert r.returncode == 0
    assert "brm-design" in r.stdout
    # Mention every subcommand.
    for cmd in (
        "init", "status", "handoff", "gate", "record-gate", "advance",
        "block", "unblock", "complete", "abandon", "list", "validate",
    ):
        assert cmd in r.stdout, f"help should mention {cmd}"


def test_unknown_subcommand_exits_2(orch: Path):
    r = _run(["bogus"], cwd=orch)
    assert r.returncode == 2
