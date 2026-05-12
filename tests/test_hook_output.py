"""Subprocess golden-output tests for the UserPromptSubmit hook."""
from __future__ import annotations

import json
import os
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_SCRIPT = REPO_ROOT / "hooks" / "on-user-prompt-submit.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "sidecars"


def _run_hook(
    prompt: str,
    *,
    home: Path,
    project_root: Path | None = None,
    cwd: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> dict:
    env = {
        **os.environ,
        "BRM_HOME": str(home),
    }
    if project_root is not None:
        env["BRM_PROJECT_ROOT"] = str(project_root)
    else:
        env.pop("BRM_PROJECT_ROOT", None)
    if extra_env:
        env.update(extra_env)
    event_obj = {"hook_event_name": "UserPromptSubmit", "prompt": prompt}
    if cwd is not None:
        event_obj["cwd"] = str(cwd)
    event = json.dumps(event_obj)
    proc = subprocess.run(
        ["python3", str(HOOK_SCRIPT)],
        input=event,
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout or "{}")


def _additional(out: dict) -> str:
    return out.get("hookSpecificOutput", {}).get("additionalContext", "")


# --- No-match cases ------------------------------------------------------

def test_no_command_emits_empty(tmp_path: Path) -> None:
    out = _run_hook("hello there", home=tmp_path, project_root=tmp_path)
    assert out == {}


def test_unknown_command_emits_empty(tmp_path: Path) -> None:
    out = _run_hook("/foo bar", home=tmp_path, project_root=tmp_path)
    assert out == {}


def test_longer_prefix_no_match(tmp_path: Path) -> None:
    out = _run_hook("/reviewer-fresh hi", home=tmp_path, project_root=tmp_path)
    assert out == {}


def test_case_sensitive_no_match(tmp_path: Path) -> None:
    out = _run_hook("/Reviewer hi", home=tmp_path, project_root=tmp_path)
    assert out == {}


# --- Match + present layer cases ----------------------------------------

def test_match_with_both_layers(tmp_path: Path) -> None:
    out = _run_hook(
        "/reviewer look at the cache change",
        home=FIXTURES / "global",
        project_root=FIXTURES / "project",
    )
    ctx = _additional(out)
    assert '<brm-sidecar role="reviewer">' in ctx
    assert '<layer scope="global"' in ctx
    assert '<layer scope="project"' in ctx
    assert "Always read tests before implementation" in ctx
    assert "Caching layer reviews must include eviction proofs" in ctx


def test_match_namespaced_command(tmp_path: Path) -> None:
    out = _run_hook(
        "/brm:reviewer look",
        home=FIXTURES / "global",
        project_root=FIXTURES / "project",
    )
    ctx = _additional(out)
    assert '<brm-sidecar role="reviewer">' in ctx


def test_match_global_only(tmp_path: Path) -> None:
    out = _run_hook(
        "/reviewer hi",
        home=FIXTURES / "global",
        project_root=tmp_path,  # no .brm here
    )
    ctx = _additional(out)
    assert '<layer scope="global"' in ctx
    assert '<layer scope="project"' not in ctx


def test_match_project_only(tmp_path: Path) -> None:
    out = _run_hook(
        "/reviewer hi",
        home=tmp_path,  # no global file
        project_root=FIXTURES / "project",
    )
    ctx = _additional(out)
    assert '<layer scope="project"' in ctx
    assert '<layer scope="global"' not in ctx


def test_match_neither_layer_emits_empty(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".brm").mkdir()  # marker but no sidecar
    out = _run_hook("/reviewer hi", home=home, project_root=proj)
    assert out == {}


# --- Robustness ----------------------------------------------------------

def test_malformed_stdin_exits_zero_empty(tmp_path: Path) -> None:
    env = {**os.environ, "BRM_HOME": str(tmp_path)}
    proc = subprocess.run(
        ["python3", str(HOOK_SCRIPT)],
        input="not json at all",
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() in ("{}", '{"hookSpecificOutput": {}}')


# --- Orchestrator scenarios ----------------------------------------------

ORCH_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "orchestrator"


def _run_hook_orch(
    prompt: str,
    *,
    home: Path,
    orchestrator_root: Path | None,
    project_root: Path | None,
) -> dict:
    env = {**os.environ, "BRM_HOME": str(home)}
    if orchestrator_root is not None:
        env["BRM_ORCHESTRATOR_ROOT"] = str(orchestrator_root)
    else:
        env.pop("BRM_ORCHESTRATOR_ROOT", None)
    if project_root is not None:
        env["BRM_PROJECT_ROOT"] = str(project_root)
    else:
        env.pop("BRM_PROJECT_ROOT", None)
    event = json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": prompt})
    proc = subprocess.run(
        ["python3", str(HOOK_SCRIPT)],
        input=event,
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout or "{}")


def test_orchestrator_block_emitted_with_cwd_repo(tmp_path: Path) -> None:
    out = _run_hook_orch(
        "/reviewer hi",
        home=tmp_path,
        orchestrator_root=ORCH_FIXTURE,
        project_root=ORCH_FIXTURE / "api",
    )
    ctx = _additional(out)
    assert '<brm-orchestrator root="' in ctx
    assert 'cwd-repo="api"' in ctx
    assert "<repos.yaml>" in ctx
    # Verbatim content present
    assert "test_command: pytest" in ctx
    assert "test_command: npm test" in ctx


def test_orchestrator_block_omits_cwd_repo_when_not_in_a_repo(tmp_path: Path) -> None:
    out = _run_hook_orch(
        "/reviewer hi",
        home=tmp_path,
        orchestrator_root=ORCH_FIXTURE,
        project_root=tmp_path,  # not under any declared path
    )
    ctx = _additional(out)
    assert "<brm-orchestrator" in ctx
    assert 'cwd-repo=' not in ctx


def test_orchestrator_three_layer_sidecar_when_all_present(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    # Seed a global layer too.
    (home / ".claude" / "brm" / "sidecars").mkdir(parents=True)
    (home / ".claude" / "brm" / "sidecars" / "reviewer.md").write_text(
        "# Global\n## Patterns\n- 2026-01-01 — global thing\n"
    )
    out = _run_hook_orch(
        "/reviewer hi",
        home=home,
        orchestrator_root=ORCH_FIXTURE,
        project_root=ORCH_FIXTURE / "api",
    )
    ctx = _additional(out)
    assert '<layer scope="global"' in ctx
    assert '<layer scope="orchestrator"' in ctx
    assert '<layer scope="project"' in ctx
    g = ctx.index('scope="global"')
    o = ctx.index('scope="orchestrator"')
    p = ctx.index('scope="project"')
    assert g < o < p


def test_orchestrator_malformed_repos_yaml_drops_block_but_keeps_sidecars(
    tmp_path: Path,
) -> None:
    bad_orch = tmp_path / "bad-orch"
    (bad_orch / ".brm" / "sidecars").mkdir(parents=True)
    (bad_orch / ".brm" / "repos.yaml").write_text("not: valid: yaml: at: all:\n  - [\n")
    (bad_orch / ".brm" / "sidecars" / "reviewer.md").write_text(
        "# bad orch sidecar\n## Patterns\n- 2026-04-15 — present\n"
    )
    out = _run_hook_orch(
        "/reviewer hi",
        home=tmp_path / "home",
        orchestrator_root=bad_orch,
        project_root=None,
    )
    ctx = _additional(out)
    assert "<brm-orchestrator" not in ctx
    assert '<layer scope="orchestrator"' in ctx  # sidecar still fires
    assert "present" in ctx


def test_orchestrator_no_orch_root_falls_back_to_v01_behavior(tmp_path: Path) -> None:
    """Sanity: explicit BRM_ORCHESTRATOR_ROOT unset → v0.1.0 behavior."""
    out = _run_hook_orch(
        "/reviewer hi",
        home=FIXTURES / "global",
        orchestrator_root=None,
        project_root=FIXTURES / "project",
    )
    ctx = _additional(out)
    assert "<brm-orchestrator" not in ctx
    assert '<brm-sidecar role="reviewer">' in ctx
    assert '<layer scope="orchestrator"' not in ctx


# --- Design block scenarios ----------------------------------------------

DESIGN_FIXTURE = textwrap.dedent("""\
    ---
    design: 2026-05-12-cache-fix
    created: 2026-05-12T14:22:00-04:00
    workflow: tdd
    repos: [api]
    description: ""
    status: in-progress
    current_phase: red-api
    phases:
      - {name: red-api, repo: api, status: in-progress, started: null, finished: null, handoff: null, gate_result: null}
      - {name: green-api, repo: api, status: planned, started: null, finished: null, handoff: null, gate_result: null}
    history: []
    ---

    # body

    ## Handoffs
""")


def test_hook_emits_brm_design_when_in_progress(tmp_path):
    orch = tmp_path / "orch"
    (orch / ".brm").mkdir(parents=True)
    (orch / ".brm" / "repos.yaml").write_text(
        "repos:\n  api:\n    path: api\n    type: api\n"
        "    default_branch: main\n    test_command: pytest\n    lint_command: ruff check\n"
    )
    (orch / "api" / ".git").mkdir(parents=True)
    designs = orch / "docs" / "superpowers" / "designs"
    designs.mkdir(parents=True)
    (designs / "2026-05-12-cache-fix.md").write_text(DESIGN_FIXTURE)

    out = _run_hook(prompt="/dev cache fix",
                    home=tmp_path / "home",
                    cwd=orch / "api",
                    extra_env={"BRM_ACTIVE_DESIGN": str(designs / "2026-05-12-cache-fix.md")})
    ctx = _additional(out)
    assert "<brm-design" in ctx
    assert 'current-phase="red-api"' in ctx
    assert "<brm-orchestrator" in ctx  # still emits


def test_hook_drops_brm_design_when_complete(tmp_path):
    orch = tmp_path / "orch"
    (orch / ".brm").mkdir(parents=True)
    (orch / ".brm" / "repos.yaml").write_text(
        "repos:\n  api:\n    path: api\n    type: api\n"
        "    default_branch: main\n    test_command: pytest\n    lint_command: ruff check\n"
    )
    (orch / "api" / ".git").mkdir(parents=True)
    designs = orch / "docs" / "superpowers" / "designs"
    designs.mkdir(parents=True)
    (designs / "done.md").write_text(DESIGN_FIXTURE.replace("status: in-progress", "status: complete"))

    out = _run_hook(prompt="/dev x",
                    home=tmp_path / "home",
                    cwd=orch / "api",
                    extra_env={"BRM_ACTIVE_DESIGN": str(designs / "done.md")})
    ctx = _additional(out)
    assert "<brm-design" not in ctx
    assert "<brm-orchestrator" in ctx
