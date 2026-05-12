"""Performance smoke tests for the BRM hook.

- Non-match path must be cheap: zero filesystem reads.
- Match path median (over 5 runs) must be under 250ms (subprocess startup
  dominates; warm cost is much lower).
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_SCRIPT = REPO_ROOT / "hooks" / "on-user-prompt-submit.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "sidecars"


def test_no_match_does_zero_sidecar_io(monkeypatch, tmp_path: Path) -> None:
    """Calling the hook helpers directly: non-match must not touch the FS.

    We exercise the pure-Python path (no subprocess) so we can monkeypatch
    Path.read_text and assert it's never called on the no-match path.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("hook_mod", HOOK_SCRIPT)
    hook_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook_mod)

    reads: list[Path] = []
    real_read = Path.read_text

    def tracked(self, *a, **kw):
        reads.append(self)
        return real_read(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", tracked)
    monkeypatch.setattr("sys.stdin", _Stdin('{"prompt": "hello world"}'))
    monkeypatch.setenv("BRM_HOME", str(tmp_path))
    monkeypatch.setenv("BRM_PROJECT_ROOT", str(tmp_path))

    rc = hook_mod.main()
    assert rc == 0
    # No reads of any .brm/sidecars/*.md should have happened.
    bad = [p for p in reads if ".brm/sidecars" in str(p) or "claude/brm" in str(p)]
    assert bad == [], f"unexpected sidecar reads on no-match path: {bad}"


class _Stdin:
    def __init__(self, payload: str) -> None:
        self._payload = payload

    def read(self) -> str:
        return self._payload


def test_match_median_under_250ms(tmp_path: Path) -> None:
    env = {
        **os.environ,
        "BRM_HOME": str(FIXTURES / "global"),
        "BRM_PROJECT_ROOT": str(FIXTURES / "project"),
    }
    event = json.dumps(
        {"hook_event_name": "UserPromptSubmit", "prompt": "/reviewer foo"}
    )
    elapsed = []
    for _ in range(5):
        t0 = time.perf_counter()
        proc = subprocess.run(
            ["python3", str(HOOK_SCRIPT)],
            input=event,
            capture_output=True,
            text=True,
            env=env,
            timeout=5,
        )
        elapsed.append(time.perf_counter() - t0)
        assert proc.returncode == 0
    elapsed.sort()
    median = elapsed[2]
    assert median < 0.25, f"hook median {median:.3f}s exceeds 250ms budget"


PERF_ORCH = Path(__file__).resolve().parent / "fixtures" / "designs" / "perf-orch"


def _run_hook_subprocess(prompt: str, *, cwd: Path, home: Path) -> str:
    env = {**os.environ, "BRM_HOME": str(home)}
    event = json.dumps({"hook_event_name": "UserPromptSubmit",
                        "prompt": prompt, "cwd": str(cwd)})
    proc = subprocess.run(
        ["python3", str(HOOK_SCRIPT)],
        input=event, capture_output=True, text=True, env=env, timeout=10,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout or "{}")
    return payload.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_hook_design_walk_under_budget(tmp_path: Path) -> None:
    home = tmp_path / "home"
    times = []
    for _ in range(11):
        start = time.perf_counter()
        out = _run_hook_subprocess(prompt="/dev x", cwd=PERF_ORCH / "api", home=home)
        elapsed_ms = (time.perf_counter() - start) * 1000
        times.append(elapsed_ms)
        assert "<brm-design" in out  # the one active design must be picked up
    times.sort()
    median = times[len(times) // 2]
    assert median < 250, f"hook median {median}ms > 250ms budget"
