"""Sidecar path resolution and file loading for BRM."""
from __future__ import annotations

import os
from pathlib import Path

ROLES: tuple[str, ...] = (
    "tea",
    "dev",
    "reviewer",
    "architect",
    "pm",
    "tech-writer",
)

_PROJECT_ROOT_WALK_CAP = 20


def find_project_root(cwd: Path) -> Path | None:
    """Return nearest ancestor of `cwd` containing `.git` or `.brm/sidecars/`.

    Walks at most _PROJECT_ROOT_WALK_CAP levels. Returns None if no marker
    is found within the cap. Note: bare `.brm/` is NOT a project-root marker;
    it may indicate an orchestrator root (which has `.brm/repos.yaml`) rather
    than a repo. The repo marker is `.git` or the presence of project-level
    `.brm/sidecars/`.
    """
    current = Path(cwd).resolve()
    for _ in range(_PROJECT_ROOT_WALK_CAP + 1):
        if (current / ".git").exists() or (current / ".brm" / "sidecars").is_dir():
            return current
        if current.parent == current:
            return None
        current = current.parent
    return None


def _read_layer(path: Path) -> str | None:
    """Read a sidecar layer; return None on any failure."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def load_sidecar(
    role: str,
    *,
    home: Path,
    project_root: Path | None,
) -> str:
    """Return concatenated `<brm-sidecar>` block for `role`, or '' if no layers.

    Global layer (`<home>/.claude/brm/sidecars/<role>.md`) is emitted first,
    project layer (`<project_root>/.brm/sidecars/<role>.md`) second. Layers
    that don't exist or can't be read are skipped silently. If neither
    layer contributes, returns an empty string.
    """
    global_path = Path(home) / ".claude" / "brm" / "sidecars" / f"{role}.md"
    project_path = (
        Path(project_root) / ".brm" / "sidecars" / f"{role}.md"
        if project_root
        else None
    )

    parts: list[str] = []

    if global_path.is_file():
        body = _read_layer(global_path)
        if body is not None:
            parts.append(
                f'  <layer scope="global" path="~/.claude/brm/sidecars/{role}.md">\n'
                f"{body.rstrip(chr(10))}\n"
                f"  </layer>"
            )

    if project_path is not None and project_path.is_file():
        body = _read_layer(project_path)
        if body is not None:
            parts.append(
                f'  <layer scope="project" path=".brm/sidecars/{role}.md">\n'
                f"{body.rstrip(chr(10))}\n"
                f"  </layer>"
            )

    if not parts:
        return ""

    inner = "\n".join(parts)
    return f'<brm-sidecar role="{role}">\n{inner}\n</brm-sidecar>\n'


def recognized_tokens() -> frozenset[str]:
    """The set of leading tokens BRM will react to."""
    out: set[str] = set()
    for role in ROLES:
        out.add(f"/{role}")
        out.add(f"/brm:{role}")
    return frozenset(out)


_RECOGNIZED = recognized_tokens()
_TOKEN_TO_ROLE: dict[str, str] = {
    **{f"/{r}": r for r in ROLES},
    **{f"/brm:{r}": r for r in ROLES},
}


def extract_command(prompt: str) -> str | None:
    """Return the leading whitespace-stripped slash token, or None."""
    stripped = prompt.lstrip()
    if not stripped.startswith("/"):
        return None
    return stripped.split(maxsplit=1)[0]


def role_for_token(token: str) -> str | None:
    """Map an exact slash-token to a role name, or None if unrecognized."""
    return _TOKEN_TO_ROLE.get(token)
