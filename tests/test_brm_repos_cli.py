"""Subprocess tests for scripts/brm-repos."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "brm-repos"


def _run(args: list[str], *, cwd: Path, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ}
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["python3", str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
    )


# --- init -----------------------------------------------------------------

def test_init_creates_repos_yaml_in_cwd(tmp_path: Path) -> None:
    proc = _run(["init"], cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / ".brm" / "repos.yaml").is_file()
    text = (tmp_path / ".brm" / "repos.yaml").read_text()
    assert "repos:" in text


def test_init_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    _run(["init"], cwd=tmp_path)
    proc = _run(["init"], cwd=tmp_path)
    assert proc.returncode == 1
    assert "exists" in (proc.stderr + proc.stdout).lower()


def test_init_force_overwrites(tmp_path: Path) -> None:
    _run(["init"], cwd=tmp_path)
    (tmp_path / ".brm" / "repos.yaml").write_text("repos:\n  marker: {}\n")
    proc = _run(["init", "--force"], cwd=tmp_path)
    assert proc.returncode == 0
    assert "marker" not in (tmp_path / ".brm" / "repos.yaml").read_text()


def test_init_from_pf_translates(tmp_path: Path) -> None:
    pf_dir = tmp_path / ".pennyfarthing"
    pf_dir.mkdir()
    (pf_dir / "repos.yaml").write_text("""\
pr_title_format: "{title}"
repos:
  api:
    path: api
    type: api
    description: REST API
    default_branch: main
    test_command: pytest
    lint_command: ruff check
    build_command: ""
    owns:
      - api/**
    never_edit:
      - node_modules/**
    ui_layer: none
""")
    proc = _run(["init", "--from-pf"], cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    out = (tmp_path / ".brm" / "repos.yaml").read_text()
    assert "api:" in out
    assert "test_command: pytest" in out
    # PF-only fields dropped
    assert "owns" not in out
    assert "never_edit" not in out
    assert "ui_layer" not in out
    assert "pr_title_format" not in out


def test_init_from_pf_missing_source_errors(tmp_path: Path) -> None:
    proc = _run(["init", "--from-pf"], cwd=tmp_path)
    assert proc.returncode == 1
    assert "pennyfarthing" in (proc.stderr + proc.stdout).lower()
