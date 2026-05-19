"""Tests for brm role CLI verbs."""
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


def test_brm_roles_list_includes_six_built_ins():
    r = _run("roles", "list")
    assert r.returncode == 0
    out = r.stdout
    for name in ("architect", "pm", "tea", "dev", "reviewer", "tech-writer"):
        assert name in out


def test_brm_roles_list_json_is_valid():
    import json
    r = _run("roles", "list", "--json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert isinstance(data, list)
    names = {row["name"] for row in data}
    assert {"architect", "pm", "tea", "dev", "reviewer", "tech-writer"} <= names


def test_brm_role_new_creates_files(tmp_path):
    r = _run("role", "new", "security-reviewer", "--kind", "tactical", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / ".brm" / "agents" / "security-reviewer.md").is_file()
    assert (tmp_path / ".claude" / "commands" / "security-reviewer.md").is_file()


def test_brm_role_new_refuses_duplicate(tmp_path):
    _run("role", "new", "x", "--kind", "tactical", cwd=tmp_path)
    r = _run("role", "new", "x", "--kind", "tactical", cwd=tmp_path)
    assert r.returncode != 0


def test_brm_role_delete_removes_custom(tmp_path):
    _run("role", "new", "x", "--kind", "tactical", cwd=tmp_path)
    r = _run("role", "delete", "x", cwd=tmp_path)
    assert r.returncode == 0
    assert not (tmp_path / ".brm" / "agents" / "x.md").exists()
    assert not (tmp_path / ".claude" / "commands" / "x.md").exists()


def test_brm_role_delete_refuses_built_in(tmp_path):
    r = _run("role", "delete", "pm", cwd=tmp_path)
    assert r.returncode != 0
