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
