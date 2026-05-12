"""Unit tests for lib/sidecar.py."""
from __future__ import annotations

from pathlib import Path

import pytest

from lib import sidecar


# --- find_project_root ----------------------------------------------------

def test_find_project_root_finds_git_dir(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    sub = tmp_path / "a" / "b" / "c"
    sub.mkdir(parents=True)
    assert sidecar.find_project_root(sub) == tmp_path


def test_find_project_root_finds_git_file(tmp_path: Path) -> None:
    # `.git` is a file in submodules / worktree linked checkouts.
    (tmp_path / ".git").write_text("gitdir: /elsewhere\n")
    sub = tmp_path / "x"
    sub.mkdir()
    assert sidecar.find_project_root(sub) == tmp_path


def test_find_project_root_finds_brm_dir(tmp_path: Path) -> None:
    (tmp_path / ".brm").mkdir()
    sub = tmp_path / "deep" / "nested"
    sub.mkdir(parents=True)
    assert sidecar.find_project_root(sub) == tmp_path


def test_find_project_root_returns_none_when_not_found(tmp_path: Path) -> None:
    # tmp_path has no .git / .brm. Walk hits root with nothing.
    sub = tmp_path / "x"
    sub.mkdir()
    assert sidecar.find_project_root(sub) is None


def test_find_project_root_caps_at_20_levels(tmp_path: Path, monkeypatch) -> None:
    # Build a 25-deep tree with a marker at the root. The cap means we don't
    # find it from the deepest leaf.
    (tmp_path / ".git").mkdir()
    deepest = tmp_path
    for i in range(25):
        deepest = deepest / f"l{i}"
        deepest.mkdir()
    assert sidecar.find_project_root(deepest) is None


def test_find_project_root_returns_cwd_itself_if_marker_present(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert sidecar.find_project_root(tmp_path) == tmp_path
