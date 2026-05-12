"""Orchestrator workspace discovery and config parsing for BRM."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


_REQUIRED_REPO_KEYS = ("path", "type", "default_branch", "test_command", "lint_command")
_OPTIONAL_REPO_KEYS = ("description", "build_command")
_KNOWN_REPO_KEYS = frozenset(_REQUIRED_REPO_KEYS + _OPTIONAL_REPO_KEYS)
_KNOWN_TOP_LEVEL_KEYS = frozenset({"repos"})


class RepoConfigError(Exception):
    """Raised when repos.yaml is malformed or missing required fields."""


@dataclass(frozen=True)
class RepoConfig:
    name: str
    path: str
    type: str
    default_branch: str
    test_command: str
    lint_command: str
    description: str = ""
    build_command: str = ""


def parse_repos_yaml(text: str) -> dict[str, RepoConfig]:
    """Parse repos.yaml text into a name → RepoConfig mapping (declaration order preserved)."""
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise RepoConfigError(f"YAML parse error: {e}") from e

    if not isinstance(doc, dict):
        raise RepoConfigError("repos.yaml must be a mapping at the top level")
    if "repos" not in doc:
        raise RepoConfigError("repos.yaml must have a top-level `repos:` key")

    for key in doc:
        if key not in _KNOWN_TOP_LEVEL_KEYS:
            print(
                f"brm: warning: unknown top-level key in repos.yaml: {key!r} (ignored)",
                file=sys.stderr,
            )

    repos_raw = doc["repos"]
    if not isinstance(repos_raw, dict) or not repos_raw:
        raise RepoConfigError("`repos:` must be a non-empty mapping")

    out: dict[str, RepoConfig] = {}
    for name, raw in repos_raw.items():
        if not isinstance(raw, dict):
            raise RepoConfigError(f"repo {name!r}: entry must be a mapping")
        missing = [k for k in _REQUIRED_REPO_KEYS if k not in raw]
        if missing:
            raise RepoConfigError(
                f"repo {name!r}: missing required field(s): {', '.join(missing)}"
            )
        for key in raw:
            if key not in _KNOWN_REPO_KEYS:
                print(
                    f"brm: warning: unknown field in repo {name!r}: {key!r} (ignored)",
                    file=sys.stderr,
                )
        out[str(name)] = RepoConfig(
            name=str(name),
            path=str(raw["path"]),
            type=str(raw["type"]),
            default_branch=str(raw["default_branch"]),
            test_command=str(raw["test_command"]),
            lint_command=str(raw["lint_command"]),
            description=str(raw.get("description", "")),
            build_command=str(raw.get("build_command", "")),
        )
    return out


_ORCHESTRATOR_WALK_CAP = 20


def find_orchestrator_root(cwd: Path) -> Path | None:
    """Return nearest ancestor of `cwd` containing `.brm/repos.yaml` (file), else None.

    Walks at most _ORCHESTRATOR_WALK_CAP levels above cwd.
    """
    current = Path(cwd).resolve()
    for _ in range(_ORCHESTRATOR_WALK_CAP + 1):
        candidate = current / ".brm" / "repos.yaml"
        if candidate.is_file():
            return current
        if current.parent == current:
            return None
        current = current.parent
    return None
