#!/usr/bin/env python3
"""BRM UserPromptSubmit hook (v0.2 — orchestrator-aware).

Detects a leading `/role` or `/brm:role` token and injects:
  1. A `<brm-sidecar>` block with up to three sidecar layers
     (global, orchestrator, project) when present.
  2. A `<brm-orchestrator>` block with the workspace's repos.yaml content
     when an orchestrator root is detected.

Any failure → exit 0 with empty output; missing context is far better than
a blocked prompt.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

HOOK_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = HOOK_DIR.parent
sys.path.insert(0, str(PLUGIN_ROOT))

from lib import sidecar as _sidecar  # noqa: E402


def _emit(additional_context: str) -> None:
    if not additional_context:
        print(json.dumps({}))
        return
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": additional_context,
        }
    }
    print(json.dumps(payload))


def _home() -> Path:
    return Path(os.environ.get("BRM_HOME") or os.path.expanduser("~"))


def _orchestrator_root(event: dict[str, Any], cwd: Path) -> Path | None:
    override = os.environ.get("BRM_ORCHESTRATOR_ROOT")
    if override:
        candidate = Path(override)
        # Trust env var only if it actually has a repos.yaml file.
        if (candidate / ".brm" / "repos.yaml").is_file():
            return candidate
        return None
    from lib import orchestrator as _orch
    return _orch.find_orchestrator_root(cwd)


def _project_root(event: dict[str, Any], cwd: Path) -> Path | None:
    override = os.environ.get("BRM_PROJECT_ROOT")
    if override:
        return Path(override)
    return _sidecar.find_project_root(cwd)


def _render_orchestrator_block(orch_root: Path, cwd: Path) -> str | None:
    """Build the <brm-orchestrator> XML block, or None on any failure."""
    try:
        from lib import orchestrator as _orch
        repos_yaml_path = orch_root / ".brm" / "repos.yaml"
        text = repos_yaml_path.read_text(encoding="utf-8", errors="replace")
        repos = _orch.parse_repos_yaml(text)
    except Exception as e:
        print(f"brm: orchestrator block skipped: {e}", file=sys.stderr)
        return None

    cwd_repo_name = None
    try:
        from lib import orchestrator as _orch
        cwd_repo_name = _orch.cwd_repo(cwd, orch_root, repos)
    except Exception:
        pass  # If cwd resolution fails, just omit the attribute.

    attrs = f'root="{orch_root}"'
    if cwd_repo_name:
        attrs += f' cwd-repo="{cwd_repo_name}"'
    return (
        f"<brm-orchestrator {attrs}>\n"
        f"<repos.yaml>\n"
        f"{text.rstrip(chr(10))}\n"
        f"</repos.yaml>\n"
        f"</brm-orchestrator>\n"
    )


def main() -> int:
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
    except Exception:
        traceback.print_exc(file=sys.stderr)
        _emit("")
        return 0

    try:
        prompt = event.get("prompt", "") or ""
        token = _sidecar.extract_command(prompt)
        if not token:
            _emit("")
            return 0
        role = _sidecar.role_for_token(token)
        if not role:
            _emit("")
            return 0

        cwd = Path(event.get("cwd") or os.getcwd())
        orch_root = _orchestrator_root(event, cwd)
        proj_root = _project_root(event, cwd)

        # Use proj_root as the effective cwd for cwd_repo resolution when available,
        # since BRM_PROJECT_ROOT / event["cwd"] may differ and proj_root is more specific.
        effective_cwd = proj_root if proj_root is not None else cwd

        sidecar_block = _sidecar.load_sidecar(
            role,
            home=_home(),
            project_root=proj_root,
            orchestrator_root=orch_root,
        )

        orchestrator_block = (
            _render_orchestrator_block(orch_root, effective_cwd) if orch_root else None
        )

        pieces: list[str] = []
        if sidecar_block:
            pieces.append(sidecar_block.rstrip("\n"))
        if orchestrator_block:
            pieces.append(orchestrator_block.rstrip("\n"))
        _emit("\n".join(pieces) + "\n" if pieces else "")
        return 0
    except Exception:
        traceback.print_exc(file=sys.stderr)
        _emit("")
        return 0


if __name__ == "__main__":
    sys.exit(main())
