"""Unit tests for lib/orchestrator.py."""
from __future__ import annotations

from pathlib import Path

import pytest

from lib import orchestrator


# --- parse_repos_yaml -----------------------------------------------------

MINIMAL_YAML = """\
repos:
  api:
    path: api
    type: api
    default_branch: main
    test_command: pytest
    lint_command: ruff check
"""

FULL_YAML = """\
repos:
  api:
    path: api
    type: api
    description: REST API server
    default_branch: main
    test_command: pytest
    lint_command: ruff check
    build_command: ""
  ui:
    path: ui
    type: ui
    description: React client
    default_branch: main
    test_command: npm test
    lint_command: npm run lint
    build_command: npm run build
"""


def test_parse_minimal_yields_one_repo() -> None:
    repos = orchestrator.parse_repos_yaml(MINIMAL_YAML)
    assert set(repos) == {"api"}
    r = repos["api"]
    assert r.name == "api"
    assert r.path == "api"
    assert r.type == "api"
    assert r.default_branch == "main"
    assert r.test_command == "pytest"
    assert r.lint_command == "ruff check"
    assert r.description == ""
    assert r.build_command == ""


def test_parse_full_yields_two_repos_in_declaration_order() -> None:
    repos = orchestrator.parse_repos_yaml(FULL_YAML)
    assert list(repos) == ["api", "ui"]
    assert repos["ui"].build_command == "npm run build"
    assert repos["api"].description == "REST API server"


def test_parse_missing_required_field_raises(capsys) -> None:
    bad = "repos:\n  api:\n    path: api\n"  # missing type, default_branch, etc.
    with pytest.raises(orchestrator.RepoConfigError) as exc:
        orchestrator.parse_repos_yaml(bad)
    assert "type" in str(exc.value) or "default_branch" in str(exc.value)


def test_parse_malformed_yaml_raises() -> None:
    with pytest.raises(orchestrator.RepoConfigError):
        orchestrator.parse_repos_yaml("not: valid: yaml: at: all:\n  - [\n")


def test_parse_missing_repos_key_raises() -> None:
    with pytest.raises(orchestrator.RepoConfigError):
        orchestrator.parse_repos_yaml("not_repos:\n  api:\n    path: api\n")


def test_parse_empty_repos_raises() -> None:
    with pytest.raises(orchestrator.RepoConfigError):
        orchestrator.parse_repos_yaml("repos: {}\n")


def test_parse_unknown_top_level_key_warns_but_succeeds(capsys) -> None:
    text = MINIMAL_YAML + "future_thing: hello\n"
    repos = orchestrator.parse_repos_yaml(text)
    assert "api" in repos
    err = capsys.readouterr().err
    assert "future_thing" in err


def test_parse_unknown_per_repo_key_warns_but_succeeds(capsys) -> None:
    text = MINIMAL_YAML.replace(
        "lint_command: ruff check\n",
        "lint_command: ruff check\n    owns:\n      - api/**\n",
    )
    repos = orchestrator.parse_repos_yaml(text)
    assert "api" in repos
    err = capsys.readouterr().err
    assert "owns" in err


# --- find_orchestrator_root ----------------------------------------------

def test_find_orchestrator_root_found_at_cwd(tmp_path: Path) -> None:
    (tmp_path / ".brm").mkdir()
    (tmp_path / ".brm" / "repos.yaml").write_text("repos: {}\n")
    assert orchestrator.find_orchestrator_root(tmp_path) == tmp_path


def test_find_orchestrator_root_found_at_ancestor(tmp_path: Path) -> None:
    (tmp_path / ".brm").mkdir()
    (tmp_path / ".brm" / "repos.yaml").write_text("repos: {}\n")
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    assert orchestrator.find_orchestrator_root(deep) == tmp_path


def test_find_orchestrator_root_returns_none_when_not_found(tmp_path: Path) -> None:
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    assert orchestrator.find_orchestrator_root(deep) is None


def test_find_orchestrator_root_caps_at_20_levels(tmp_path: Path) -> None:
    (tmp_path / ".brm").mkdir()
    (tmp_path / ".brm" / "repos.yaml").write_text("repos: {}\n")
    deepest = tmp_path
    for i in range(25):
        deepest = deepest / f"l{i}"
        deepest.mkdir()
    assert orchestrator.find_orchestrator_root(deepest) is None


def test_find_orchestrator_root_nested_inner_wins(tmp_path: Path) -> None:
    # outer has .brm/repos.yaml
    (tmp_path / ".brm").mkdir()
    (tmp_path / ".brm" / "repos.yaml").write_text("repos: {}\n")
    # inner also has .brm/repos.yaml
    inner = tmp_path / "inner"
    inner.mkdir()
    (inner / ".brm").mkdir()
    (inner / ".brm" / "repos.yaml").write_text("repos: {}\n")
    deep = inner / "x"
    deep.mkdir()
    assert orchestrator.find_orchestrator_root(deep) == inner


def test_find_orchestrator_root_ignores_dir_named_repos_yaml(tmp_path: Path) -> None:
    # If someone created a *directory* called repos.yaml, don't match.
    (tmp_path / ".brm").mkdir()
    (tmp_path / ".brm" / "repos.yaml").mkdir()
    assert orchestrator.find_orchestrator_root(tmp_path) is None


# --- cwd_repo -------------------------------------------------------------

def _make_repos(spec: dict[str, str]) -> dict[str, orchestrator.RepoConfig]:
    """Build a tiny repos map for cwd_repo testing. spec = {name: path}."""
    return {
        name: orchestrator.RepoConfig(
            name=name,
            path=path,
            type="x",
            default_branch="main",
            test_command="",
            lint_command="",
        )
        for name, path in spec.items()
    }


def test_cwd_repo_matches_when_cwd_inside_declared_path(tmp_path: Path) -> None:
    orch = tmp_path
    (orch / "api").mkdir()
    cwd = orch / "api" / "src"
    cwd.mkdir()
    repos = _make_repos({"api": "api", "ui": "ui"})
    assert orchestrator.cwd_repo(cwd, orch, repos) == "api"


def test_cwd_repo_matches_at_repo_root(tmp_path: Path) -> None:
    orch = tmp_path
    (orch / "ui").mkdir()
    repos = _make_repos({"ui": "ui"})
    assert orchestrator.cwd_repo(orch / "ui", orch, repos) == "ui"


def test_cwd_repo_none_when_cwd_outside_declared_paths(tmp_path: Path) -> None:
    orch = tmp_path
    (orch / "api").mkdir()
    repos = _make_repos({"api": "api"})
    other = orch / "scratch"
    other.mkdir()
    assert orchestrator.cwd_repo(other, orch, repos) is None


def test_cwd_repo_path_dot_matches_orchestrator_root(tmp_path: Path) -> None:
    orch = tmp_path
    repos = _make_repos({"orch": ".", "api": "api"})
    (orch / "api").mkdir()
    # cwd at orch root
    assert orchestrator.cwd_repo(orch, orch, repos) == "orch"
    # cwd inside api should still match api, not orch (closest ancestor wins)
    assert orchestrator.cwd_repo(orch / "api", orch, repos) == "api"


def test_cwd_repo_nested_paths_closest_wins(tmp_path: Path) -> None:
    orch = tmp_path
    (orch / "x" / "y").mkdir(parents=True)
    repos = _make_repos({"outer": "x", "inner": "x/y"})
    cwd = orch / "x" / "y" / "deep"
    cwd.mkdir()
    assert orchestrator.cwd_repo(cwd, orch, repos) == "inner"
