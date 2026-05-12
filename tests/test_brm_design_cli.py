"""Subprocess tests for scripts/brm-design."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "brm-design"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "designs" / "orchestrator"


def _run(args, *, cwd, env=None, input_text=None):
    env = {**os.environ, **(env or {})}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd),
        env=env,
        input=input_text,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def orch(tmp_path: Path) -> Path:
    target = tmp_path / "orch"
    shutil.copytree(FIXTURE, target)
    return target


def test_script_exists_and_executable():
    assert SCRIPT.is_file()
    assert os.access(SCRIPT, os.X_OK), "scripts/brm-design must be executable"


def test_help_exits_zero(orch: Path):
    r = _run(["--help"], cwd=orch)
    assert r.returncode == 0
    assert "brm-design" in r.stdout
    # Mention every subcommand.
    for cmd in (
        "init", "status", "handoff", "gate", "record-gate", "advance",
        "block", "unblock", "complete", "abandon", "list", "validate",
    ):
        assert cmd in r.stdout, f"help should mention {cmd}"


def test_unknown_subcommand_exits_2(orch: Path):
    r = _run(["bogus"], cwd=orch)
    assert r.returncode == 2


def _load_fm(path: Path) -> dict:
    """Read a design file and return its parsed frontmatter dict."""
    import yaml as _yaml
    text = path.read_text(encoding="utf-8")
    fm_text = text.split("---", 2)[1]
    return _yaml.safe_load(fm_text)


def test_init_single_repo(orch: Path):
    r = _run(
        ["init", "x", "--workflow", "tdd", "--repos", "api"],
        cwd=orch / "api",
    )
    assert r.returncode == 0, r.stderr
    designs = list((orch / "docs" / "superpowers" / "designs").glob("*-x.md"))
    assert len(designs) == 1
    fm = _load_fm(designs[0])
    assert fm["workflow"] == "tdd"
    assert fm["repos"] == ["api"]
    assert fm["status"] == "in-progress"  # init starts the design
    assert fm["current_phase"] == "red-api"
    assert fm["phases"][0]["status"] == "in-progress"
    assert fm["phases"][0]["started"] is not None
    assert any(p["name"] == "red-api" for p in fm["phases"])
    assert any(p["name"] == "green-api" for p in fm["phases"])


def test_init_multi_repo(orch: Path):
    r = _run(
        ["init", "y", "--workflow", "tdd", "--repos", "api,ui"],
        cwd=orch,
    )
    assert r.returncode == 0, r.stderr
    designs = list((orch / "docs" / "superpowers" / "designs").glob("*-y.md"))
    fm = _load_fm(designs[0])
    names = [p["name"] for p in fm["phases"]]
    assert names == ["red-api", "red-ui", "green-api", "green-ui", "review", "finish"]
    review = next(p for p in fm["phases"] if p["name"] == "review")
    assert review["repos"] == ["api", "ui"]


def test_init_refuses_existing_without_force(orch: Path):
    args = ["init", "z", "--workflow", "tdd", "--repos", "api"]
    r1 = _run(args, cwd=orch)
    assert r1.returncode == 0, r1.stderr
    r2 = _run(args, cwd=orch)
    assert r2.returncode == 1
    assert "exists" in r2.stderr.lower()


def test_init_force_overwrites(orch: Path):
    args = ["init", "w", "--workflow", "tdd", "--repos", "api"]
    _run(args, cwd=orch)
    r = _run(args + ["--force"], cwd=orch)
    assert r.returncode == 0, r.stderr


def test_init_unknown_workflow(orch: Path):
    r = _run(["init", "q", "--workflow", "no-such", "--repos", "api"], cwd=orch)
    assert r.returncode == 1
    assert "not found" in r.stderr.lower()


def test_status_text(orch: Path):
    _run(["init", "s", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    design_path = next((orch / "docs" / "superpowers" / "designs").glob("*-s.md"))
    r = _run(["status", str(design_path)], cwd=orch)
    assert r.returncode == 0
    assert "tdd" in r.stdout
    assert "red-api" in r.stdout
    assert "planned" in r.stdout


def test_status_json_shape(orch: Path):
    _run(["init", "j", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    design_path = next((orch / "docs" / "superpowers" / "designs").glob("*-j.md"))
    r = _run(["status", str(design_path), "--json"], cwd=orch)
    assert r.returncode == 0
    payload = json.loads(r.stdout)
    assert payload["workflow"] == "tdd"
    assert payload["current_phase"] == "red-api"
    assert payload["repos"] == ["api"]
    assert isinstance(payload["phases"], list)


def test_status_auto_discovers_active(orch: Path):
    _run(["init", "auto", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    # init produces status: in-progress, so the design is immediately active.
    r = _run(["status"], cwd=orch / "api")
    assert r.returncode == 0
    assert "auto" in r.stdout


def test_status_no_active_returns_2(orch: Path):
    r = _run(["status"], cwd=orch / "api")
    assert r.returncode == 2
    assert "no active design" in r.stderr.lower()


SAMPLE_HANDOFF = (
    '<handoff from="red-api" to="green-api" repo="api" agent="tea" '
    'at="2026-05-12T10:00:00-04:00">\n'
    'Summary: 3 failing tests added.\n'
    'Test status: failing=3 passing=0 skipped=0\n'
    '</handoff>\n'
)


def test_handoff_inserts_anchor(orch: Path):
    _run(["init", "h", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    design_path = next((orch / "docs" / "superpowers" / "designs").glob("*-h.md"))
    r = _run(
        ["handoff", str(design_path), "--from", "red-api", "--to", "green-api", "--stdin"],
        cwd=orch, input_text=SAMPLE_HANDOFF,
    )
    assert r.returncode == 0, r.stderr
    text = design_path.read_text()
    assert "{#handoffs/red-api}" in text
    assert "Summary: 3 failing tests" in text
    assert 'handoff: "#handoffs/red-api"' in text or "handoff: '#handoffs/red-api'" in text


def test_handoff_rejects_malformed_xml(orch: Path):
    _run(["init", "h2", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    design_path = next((orch / "docs" / "superpowers" / "designs").glob("*-h2.md"))
    r = _run(
        ["handoff", str(design_path), "--from", "red-api", "--to", "green-api", "--stdin"],
        cwd=orch, input_text="not a handoff\n",
    )
    assert r.returncode == 1
    assert "handoff" in r.stderr.lower()


def test_handoff_from_file(orch: Path, tmp_path: Path):
    _run(["init", "hf", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    design_path = next((orch / "docs" / "superpowers" / "designs").glob("*-hf.md"))
    hf = tmp_path / "h.xml"
    hf.write_text(SAMPLE_HANDOFF)
    r = _run(
        ["handoff", str(design_path), "--from", "red-api", "--to", "green-api",
         "--file", str(hf)],
        cwd=orch,
    )
    assert r.returncode == 0, r.stderr


GOOD_GATE_RESULT = (
    'GATE_RESULT:\n'
    '  status: pass\n'
    '  gate: tests-fail\n'
    '  repo: api\n'
    '  message: "All ACs covered"\n'
)

BAD_GATE_RESULT = "no GATE_RESULT block here\n"


def test_gate_emits_prompt_with_context(orch: Path):
    _run(["init", "g", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    design_path = next((orch / "docs" / "superpowers" / "designs").glob("*-g.md"))
    # init already starts the first phase, so the gate has context.
    r = _run(["gate", str(design_path)], cwd=orch / "api")
    assert r.returncode == 0
    assert "<gate-context>" in r.stdout
    assert 'repo="api"' in r.stdout
    assert "tests-fail" in r.stdout


def test_record_gate_pass(orch: Path):
    _run(["init", "rg", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    design_path = next((orch / "docs" / "superpowers" / "designs").glob("*-rg.md"))
    r = _run(
        ["record-gate", str(design_path), "--result-stdin"],
        cwd=orch, input_text=GOOD_GATE_RESULT,
    )
    assert r.returncode == 0, r.stderr
    fm = _load_fm(design_path)
    red = next(p for p in fm["phases"] if p["name"] == "red-api")
    assert red["gate_result"] == "pass"
    assert any(h["event"] == "gate-pass" for h in fm["history"])


def test_record_gate_default_deny(orch: Path):
    _run(["init", "rgd", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    design_path = next((orch / "docs" / "superpowers" / "designs").glob("*-rgd.md"))
    r = _run(
        ["record-gate", str(design_path), "--result-stdin"],
        cwd=orch, input_text=BAD_GATE_RESULT,
    )
    assert r.returncode == 1
    # Default-deny: malformed result must not be persisted.
    fm = _load_fm(design_path)
    red = next(p for p in fm["phases"] if p["name"] == "red-api")
    assert red["gate_result"] is None


def test_advance_after_pass(orch: Path):
    _run(["init", "a", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    design_path = next((orch / "docs" / "superpowers" / "designs").glob("*-a.md"))
    _run(["record-gate", str(design_path), "--result-stdin"],
         cwd=orch, input_text=GOOD_GATE_RESULT)
    r = _run(["advance", str(design_path), "--to", "green-api"], cwd=orch)
    assert r.returncode == 0, r.stderr
    fm = _load_fm(design_path)
    assert fm["current_phase"] == "green-api"


def test_advance_without_gate_rejected(orch: Path):
    _run(["init", "b", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    design_path = next((orch / "docs" / "superpowers" / "designs").glob("*-b.md"))
    r = _run(["advance", str(design_path), "--to", "green-api"], cwd=orch)
    assert r.returncode == 1
    assert "gate" in r.stderr.lower()


def test_advance_force(orch: Path):
    _run(["init", "c", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    design_path = next((orch / "docs" / "superpowers" / "designs").glob("*-c.md"))
    r = _run(
        ["advance", str(design_path), "--to", "green-api", "--force"],
        cwd=orch,
    )
    assert r.returncode == 0
    fm = _load_fm(design_path)
    assert any(h["event"] == "phase-skip" for h in fm["history"])


def test_block_unblock_round_trip(orch: Path):
    _run(["init", "bu", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    design_path = next((orch / "docs" / "superpowers" / "designs").glob("*-bu.md"))
    r1 = _run(["block", str(design_path), "--reason", "waiting"], cwd=orch)
    assert r1.returncode == 0
    assert _load_fm(design_path)["status"] == "blocked"
    r2 = _run(["unblock", str(design_path)], cwd=orch)
    assert r2.returncode == 0
    assert _load_fm(design_path)["status"] == "in-progress"


def test_abandon(orch: Path):
    _run(["init", "ab", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    design_path = next((orch / "docs" / "superpowers" / "designs").glob("*-ab.md"))
    r = _run(["abandon", str(design_path), "--reason", "obsolete"], cwd=orch)
    assert r.returncode == 0
    assert _load_fm(design_path)["status"] == "abandoned"


def test_complete_rejected_when_phases_pending(orch: Path):
    _run(["init", "cp", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    design_path = next((orch / "docs" / "superpowers" / "designs").glob("*-cp.md"))
    r = _run(["complete", str(design_path)], cwd=orch)
    assert r.returncode == 1
    assert "complete" in r.stderr.lower()


def test_list_filters_by_status(orch: Path):
    _run(["init", "l1", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    _run(["init", "l2", "--workflow", "tdd", "--repos", "ui"], cwd=orch)
    # Mark l1 as planned (not in-progress).
    p1 = next((orch / "docs" / "superpowers" / "designs").glob("*-l1.md"))
    p1.write_text(p1.read_text().replace("status: in-progress", "status: planned", 1))
    r = _run(["list", "--status", "in-progress"], cwd=orch)
    assert r.returncode == 0
    assert "l2" in r.stdout
    assert "l1" not in r.stdout


def test_list_filters_by_repo(orch: Path):
    _run(["init", "r1", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    _run(["init", "r2", "--workflow", "tdd", "--repos", "ui"], cwd=orch)
    r = _run(["list", "--repo", "ui"], cwd=orch)
    assert r.returncode == 0
    assert "r2" in r.stdout
    assert "r1" not in r.stdout


def test_list_json(orch: Path):
    _run(["init", "j1", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    r = _run(["list", "--json"], cwd=orch)
    assert r.returncode == 0
    arr = json.loads(r.stdout)
    assert isinstance(arr, list)
    assert any("j1" in item.get("design", "") for item in arr)


def test_validate_clean(orch: Path):
    _run(["init", "v1", "--workflow", "tdd", "--repos", "api"], cwd=orch)
    p = next((orch / "docs" / "superpowers" / "designs").glob("*-v1.md"))
    r = _run(["validate", str(p)], cwd=orch)
    assert r.returncode == 0


def test_validate_corrupt(orch: Path, tmp_path: Path):
    bad = tmp_path / "bad.md"
    bad.write_text("not a design\n")
    r = _run(["validate", str(bad)], cwd=orch)
    assert r.returncode == 1
