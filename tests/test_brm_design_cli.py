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


def _load_fm(path: Path) -> dict:
    """Read a design file and return its parsed frontmatter dict."""
    import yaml as _yaml
    text = path.read_text(encoding="utf-8")
    fm_text = text.split("---", 2)[1]
    return _yaml.safe_load(fm_text)


def test_init_single_repo(orch: Path):
    r = _run(
        ["init", "x", "--workflow", "tdd", "--repos", "api"],
        cwd=orch / "api",
    )
    assert r.returncode == 0, r.stderr
    designs = list((orch / "docs" / "superpowers" / "designs").glob("*-x.md"))
    assert len(designs) == 1
    fm = _load_fm(designs[0])
    assert fm["workflow"] == "tdd"
    assert fm["repos"] == ["api"]
    assert fm["status"] == "in-progress"  # init starts the design
    assert fm["current_phase"] == "red-api"
    assert fm["phases"][0]["status"] == "in-progress"
    assert fm["phases"][0]["started"] is not None
    assert any(p["name"] == "red-api" for p in fm["phases"])
    assert any(p["name"] == "green-api" for p in fm["phases"])


def test_init_multi_repo(orch: Path):
    r = _run(
        ["init", "y", "--workflow", "tdd", "--repos", "api,ui"],
        cwd=orch,
    )
    assert r.returncode == 0, r.stderr
    designs = list((orch / "docs" / "superpowers" / "designs").glob("*-y.md"))
    fm = _load_fm(designs[0])
    names = [p["name"] for p in fm["phases"]]
    assert names == ["red-api", "red-ui", "green-api", "green-ui", "review", "finish"]
    review = next(p for p in fm["phases"] if p["name"] == "review")
    assert review["repos"] == ["api", "ui"]


def test_init_refuses_existing_without_force(orch: Path):
    args = ["init", "z", "--workflow", "tdd", "--repos", "api"]
    r1 = _run(args, cwd=orch)
    assert r1.returncode == 0, r1.stderr
    r2 = _run(args, cwd=orch)
    assert r2.returncode == 1
    assert "exists" in r2.stderr.lower()


def test_init_force_overwrites(orch: Path):
    args = ["init", "w", "--workflow", "tdd", "--repos", "api"]
    _run(args, cwd=orch)
    r = _run(args + ["--force"], cwd=orch)
    assert r.returncode == 0, r.stderr


def test_init_unknown_workflow(orch: Path):
    r = _run(["init", "q", "--workflow", "no-such", "--repos", "api"], cwd=orch)
    assert r.returncode == 1
    assert "not found" in r.stderr.lower()


def test_status_text(orch: Path):
    _run(["init", "s", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    design_path = next((orch / "docs" / "superpowers" / "designs").glob("*-s.md"))
    r = _run(["status", str(design_path)], cwd=orch)
    assert r.returncode == 0
    assert "tdd" in r.stdout
    assert "red-api" in r.stdout
    assert "planned" in r.stdout


def test_status_json_shape(orch: Path):
    _run(["init", "j", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    design_path = next((orch / "docs" / "superpowers" / "designs").glob("*-j.md"))
    r = _run(["status", str(design_path), "--json"], cwd=orch)
    assert r.returncode == 0
    payload = json.loads(r.stdout)
    assert payload["workflow"] == "tdd"
    assert payload["current_phase"] == "red-api"
    assert payload["repos"] == ["api"]
    assert isinstance(payload["phases"], list)


def test_status_auto_discovers_active(orch: Path):
    _run(["init", "auto", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    # init produces status: in-progress, so the design is immediately active.
    r = _run(["status"], cwd=orch / "api")
    assert r.returncode == 0
    assert "auto" in r.stdout


def test_status_no_active_returns_2(orch: Path):
    r = _run(["status"], cwd=orch / "api")
    assert r.returncode == 2
    assert "no active design" in r.stderr.lower()
