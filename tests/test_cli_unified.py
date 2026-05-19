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


@pytest.mark.xfail(strict=True, reason="Nouns register in later phases; remove after Phase G")
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
