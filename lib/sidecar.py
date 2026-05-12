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
    """Return nearest ancestor of `cwd` containing `.git` or `.brm/`.

    Walks at most _PROJECT_ROOT_WALK_CAP levels. Returns None if no marker
    is found within the cap.
    """
    current = Path(cwd).resolve()
    for _ in range(_PROJECT_ROOT_WALK_CAP + 1):
        if (current / ".git").exists() or (current / ".brm").is_dir():
            return current
        if current.parent == current:
            return None
        current = current.parent
    return None
