#!/usr/bin/env python3
"""BRM UserPromptSubmit hook.

Detects a leading `/role` or `/brm:role` token and injects the corresponding
sidecar content as `additionalContext`. Any failure → exit 0 with empty
output; missing context is far better than a blocked prompt.
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
    """Write the hook response to stdout."""
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


def _project_root(event: dict[str, Any]) -> Path | None:
    override = os.environ.get("BRM_PROJECT_ROOT")
    if override:
        # Override is treated as an authoritative root, regardless of markers.
        return Path(override)
    cwd_str = event.get("cwd") or os.getcwd()
    return _sidecar.find_project_root(Path(cwd_str))


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
        content = _sidecar.load_sidecar(
            role,
            home=_home(),
            project_root=_project_root(event),
        )
        _emit(content)
        return 0
    except Exception:
        traceback.print_exc(file=sys.stderr)
        _emit("")
        return 0


if __name__ == "__main__":
    sys.exit(main())
