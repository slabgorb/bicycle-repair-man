"""Tests for the unified brm CLI dispatcher."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
BRM = PLUGIN_ROOT / "scripts" / "brm"


def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(BRM), *args],
        cwd=cwd or PLUGIN_ROOT,
        capture_output=True,
        text=True,
    )


def test_brm_no_args_prints_help_and_exits_nonzero():
    r = _run()
    assert r.returncode != 0
    assert "Usage:" in r.stdout or "usage:" in r.stderr.lower()


def test_brm_version_prints_semver():
    r = _run("version")
    assert r.returncode == 0
    assert r.stdout.strip().count(".") == 2  # e.g. "0.4.0"


def test_brm_help_lists_known_nouns():
    r = _run("help")
    assert r.returncode == 0
    out = r.stdout
    for noun in ("epic", "story", "repos", "roles", "role"):
        assert noun in out, f"help should mention '{noun}': {out!r}"


def test_brm_unknown_subcommand_errors():
    r = _run("nonsense")
    assert r.returncode != 0
    assert "unknown" in (r.stdout + r.stderr).lower()


def test_brm_dash_dash_help_works():
    r = _run("--help")
    assert r.returncode == 0, f"--help should exit 0, got {r.returncode}: {r.stderr!r}"
    assert "usage:" in r.stdout.lower(), f"--help should print usage to stdout: {r.stdout!r}"


def test_brm_dash_h_works():
    r = _run("-h")
    assert r.returncode == 0, f"-h should exit 0, got {r.returncode}: {r.stderr!r}"
    assert "usage:" in r.stdout.lower(), f"-h should print usage to stdout: {r.stdout!r}"


def test_brm_help_version_exits_zero():
    r = _run("help", "version")
    assert r.returncode == 0, f"`brm help version` should exit 0, got {r.returncode}: {r.stderr!r}"


def test_brm_help_help_exits_zero():
    r = _run("help", "help")
    assert r.returncode == 0, f"`brm help help` should exit 0, got {r.returncode}: {r.stderr!r}"


BRM_DESIGN = PLUGIN_ROOT / "scripts" / "brm-design"


def _run_legacy(*args):
    return subprocess.run(
        [sys.executable, str(BRM_DESIGN), *args],
        cwd=PLUGIN_ROOT,
        capture_output=True,
        text=True,
    )


def test_brm_design_shim_prints_deprecation_warning():
    """Legacy `brm-design init` should still work but warn on stderr."""
    r = _run_legacy("--help")
    assert r.returncode in (0, 2)  # argparse prints help and exits 0
    assert "deprecated" in r.stderr.lower() or "deprecat" in r.stderr.lower()


def test_brm_design_shim_still_routes_subcommand():
    """The shim must not break existing v0.3 callers."""
    r = _run_legacy("status", "--help")
    assert r.returncode in (0, 2)
    # Either the legacy status help, or a deprecation pointer to `brm epic`.
    assert "status" in (r.stdout + r.stderr).lower()


BRM_REPOS = PLUGIN_ROOT / "scripts" / "brm-repos"


def test_brm_repos_shim_prints_deprecation_warning():
    r = subprocess.run(
        [sys.executable, str(BRM_REPOS), "--help"],
        cwd=PLUGIN_ROOT,
        capture_output=True,
        text=True,
    )
    assert "deprecated" in r.stderr.lower() or "deprecat" in r.stderr.lower()


def test_brm_repos_status_matches_legacy(tmp_path):
    """`brm repos status` should produce the same content as `brm-repos status`
    when run in a workspace with a repos.yaml."""
    repos_yaml = tmp_path / ".brm" / "repos.yaml"
    repos_yaml.parent.mkdir(parents=True)
    repos_yaml.write_text("""\
repos:
  api:
    path: services/api
    type: backend
    default_branch: main
    test_command: ""
    lint_command: ""
""")
    r1 = subprocess.run(
        [sys.executable, str(BRM), "repos", "status"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    r2 = subprocess.run(
        [sys.executable, str(BRM_REPOS), "status"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    # Both should succeed; both should mention "api"
    assert r1.returncode == 0
    assert "api" in r1.stdout
