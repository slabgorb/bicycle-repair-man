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


# --- list / topology / describe / owns ------------------------------------

ORCH_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "orchestrator"


def _orch_env(orch_root: Path) -> dict:
    return {"BRM_ORCHESTRATOR_ROOT": str(orch_root)}


def test_list_prints_repo_names(tmp_path: Path) -> None:
    proc = _run(["list"], cwd=tmp_path, env_extra=_orch_env(ORCH_FIXTURE))
    assert proc.returncode == 0, proc.stderr
    names = proc.stdout.split()
    assert "api" in names and "ui" in names


def test_list_json(tmp_path: Path) -> None:
    proc = _run(["list", "--json"], cwd=tmp_path, env_extra=_orch_env(ORCH_FIXTURE))
    data = json.loads(proc.stdout)
    assert {r["name"] for r in data} == {"api", "ui"}
    assert all("path" in r and "type" in r for r in data)


def test_topology_prints_verbatim(tmp_path: Path) -> None:
    proc = _run(["topology"], cwd=tmp_path, env_extra=_orch_env(ORCH_FIXTURE))
    assert proc.returncode == 0
    assert "test_command: pytest" in proc.stdout
    assert "test_command: npm test" in proc.stdout


def test_topology_json(tmp_path: Path) -> None:
    proc = _run(["topology", "--json"], cwd=tmp_path, env_extra=_orch_env(ORCH_FIXTURE))
    data = json.loads(proc.stdout)
    assert set(data["repos"]) == {"api", "ui"}


def test_describe_known_repo(tmp_path: Path) -> None:
    proc = _run(["describe", "api"], cwd=tmp_path, env_extra=_orch_env(ORCH_FIXTURE))
    assert proc.returncode == 0
    assert "test_command: pytest" in proc.stdout


def test_describe_unknown_repo_exits_2(tmp_path: Path) -> None:
    proc = _run(["describe", "nope"], cwd=tmp_path, env_extra=_orch_env(ORCH_FIXTURE))
    assert proc.returncode == 2


def test_owns_path_inside_repo(tmp_path: Path) -> None:
    # ORCH_FIXTURE/api/some/file.py — note: file need not exist, owns is path-based
    target = str(ORCH_FIXTURE / "api" / "some" / "file.py")
    proc = _run(["owns", target], cwd=tmp_path, env_extra=_orch_env(ORCH_FIXTURE))
    assert proc.returncode == 0
    assert proc.stdout.strip() == "api"


def test_owns_path_outside_repos_exits_2(tmp_path: Path) -> None:
    target = str(ORCH_FIXTURE / "scratch" / "file.txt")
    proc = _run(["owns", target], cwd=tmp_path, env_extra=_orch_env(ORCH_FIXTURE))
    assert proc.returncode == 2


def test_commands_require_orchestrator_workspace(tmp_path: Path) -> None:
    # No env var, cwd has no .brm/repos.yaml.
    proc = _run(["list"], cwd=tmp_path)
    assert proc.returncode == 1
    assert "orchestrator" in (proc.stderr + proc.stdout).lower()


# --- status / snapshot / branch -------------------------------------------

def _git_init_repo(path: Path, *, default_branch: str = "main") -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", default_branch, str(path)], check=True)
    (path / "README.md").write_text(f"# {path.name}\n")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(path), "-c", "user.email=a@b.c", "-c", "user.name=t",
         "commit", "-q", "-m", "init"], check=True
    )


def _build_orch_with_git_repos(root: Path) -> None:
    (root / ".brm").mkdir(parents=True)
    (root / ".brm" / "repos.yaml").write_text("""\
repos:
  api:
    path: api
    type: api
    default_branch: main
    test_command: ""
    lint_command: ""
  ui:
    path: ui
    type: ui
    default_branch: main
    test_command: ""
    lint_command: ""
""")
    _git_init_repo(root / "api")
    _git_init_repo(root / "ui")


def test_status_clean_exits_zero(tmp_path: Path) -> None:
    _build_orch_with_git_repos(tmp_path)
    proc = _run(["status"], cwd=tmp_path, env_extra=_orch_env(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert "api" in proc.stdout
    assert "ui" in proc.stdout


def test_status_dirty_exits_one(tmp_path: Path) -> None:
    _build_orch_with_git_repos(tmp_path)
    (tmp_path / "api" / "scratch.txt").write_text("uncommitted\n")
    proc = _run(["status"], cwd=tmp_path, env_extra=_orch_env(tmp_path))
    assert proc.returncode == 1


def test_status_brief_one_line_per_repo(tmp_path: Path) -> None:
    _build_orch_with_git_repos(tmp_path)
    proc = _run(["status", "--brief"], cwd=tmp_path, env_extra=_orch_env(tmp_path))
    assert proc.returncode == 0
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    # one line per repo (≥2 lines; allow a header)
    assert any("api" in ln for ln in lines)
    assert any("ui" in ln for ln in lines)


def test_snapshot_creates_branches_in_dirty_repos(tmp_path: Path) -> None:
    _build_orch_with_git_repos(tmp_path)
    (tmp_path / "api" / "scratch.txt").write_text("work in progress\n")
    proc = _run(["snapshot", "--label", "wip"], cwd=tmp_path,
                env_extra=_orch_env(tmp_path))
    assert proc.returncode == 0, proc.stderr
    api_branches = subprocess.run(
        ["git", "-C", str(tmp_path / "api"), "branch", "--list"],
        capture_output=True, text=True, check=True
    ).stdout
    ui_branches = subprocess.run(
        ["git", "-C", str(tmp_path / "ui"), "branch", "--list"],
        capture_output=True, text=True, check=True
    ).stdout
    assert "snapshot/" in api_branches and "wip" in api_branches
    assert "snapshot/" not in ui_branches  # ui was clean


def test_branch_creates_in_all_repos(tmp_path: Path) -> None:
    _build_orch_with_git_repos(tmp_path)
    proc = _run(["branch", "feat/x"], cwd=tmp_path, env_extra=_orch_env(tmp_path))
    assert proc.returncode == 0, proc.stderr
    for repo in ("api", "ui"):
        out = subprocess.run(
            ["git", "-C", str(tmp_path / repo), "branch", "--list", "feat/x"],
            capture_output=True, text=True, check=True
        ).stdout
        assert "feat/x" in out, f"{repo}: branch not created"


def test_branch_repos_filter_csv(tmp_path: Path) -> None:
    _build_orch_with_git_repos(tmp_path)
    proc = _run(["branch", "feat/api-only", "--repos", "api"], cwd=tmp_path,
                env_extra=_orch_env(tmp_path))
    assert proc.returncode == 0
    api_out = subprocess.run(
        ["git", "-C", str(tmp_path / "api"), "branch", "--list", "feat/api-only"],
        capture_output=True, text=True, check=True
    ).stdout
    ui_out = subprocess.run(
        ["git", "-C", str(tmp_path / "ui"), "branch", "--list", "feat/api-only"],
        capture_output=True, text=True, check=True
    ).stdout
    assert "feat/api-only" in api_out
    assert "feat/api-only" not in ui_out
