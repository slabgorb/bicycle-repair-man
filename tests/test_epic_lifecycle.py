"""Tests for the Epic data model and lifecycle."""
from __future__ import annotations

import pytest

from lib import epic as _epic

EPIC_TEXT = """---
schema: brm-epic/0.4
slug: 2026-05-19-test-epic
title: Test epic
status: draft
workflow: tdd
repos: [brm]
created: 2026-05-19
---

# Test epic

Body content.
"""


def test_parse_minimal_epic():
    e = _epic.parse_epic_text(EPIC_TEXT)
    assert e.slug == "2026-05-19-test-epic"
    assert e.title == "Test epic"
    assert e.status == "draft"
    assert e.workflow == "tdd"
    assert e.repos == ["brm"]
    assert "Body content." in e.body


def test_parse_missing_required_field_raises():
    bad = EPIC_TEXT.replace("workflow: tdd\n", "")
    with pytest.raises(_epic.EpicSchemaError, match="workflow"):
        _epic.parse_epic_text(bad)


def test_parse_invalid_status_raises():
    bad = EPIC_TEXT.replace("status: draft", "status: nonsense")
    with pytest.raises(_epic.EpicSchemaError, match="status"):
        _epic.parse_epic_text(bad)


def test_serialize_roundtrip():
    e = _epic.parse_epic_text(EPIC_TEXT)
    out = _epic.serialize_epic(e)
    e2 = _epic.parse_epic_text(out)
    assert e2.slug == e.slug
    assert e2.title == e.title
    assert e2.status == e.status
    assert e2.workflow == e.workflow
    assert e2.repos == e.repos
    assert "Body content." in e2.body


def test_spec_approval_optional():
    e = _epic.parse_epic_text(EPIC_TEXT)
    assert e.spec_approval is None  # default


def test_spec_approval_parsed_when_present():
    with_approval = EPIC_TEXT.replace(
        "created: 2026-05-19\n",
        "created: 2026-05-19\nspec_approval:\n  required: true\n  approved_at: 2026-05-19T14:22:00Z\n  approver: keith\n",
    )
    e = _epic.parse_epic_text(with_approval)
    assert e.spec_approval is not None
    assert e.spec_approval.required is True
    assert e.spec_approval.approved_at == "2026-05-19T14:22:00Z"
    assert e.spec_approval.approver == "keith"


def test_spec_approval_normalizes_offset_datetime():
    with_offset = EPIC_TEXT.replace(
        "created: 2026-05-19\n",
        "created: 2026-05-19\nspec_approval:\n  required: true\n  approved_at: 2026-05-19T16:22:00+02:00\n  approver: keith\n",
    )
    e = _epic.parse_epic_text(with_offset)
    assert e.spec_approval is not None
    assert e.spec_approval.approved_at == "2026-05-19T14:22:00Z"


# ---------------------------------------------------------------------------
# CLI tests — brm epic create
# ---------------------------------------------------------------------------

import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
BRM = PLUGIN_ROOT / "scripts" / "brm"


def _run_brm(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(BRM), *args],
        cwd=cwd, capture_output=True, text=True,
    )


def test_brm_epic_create_makes_folder_and_file(tmp_path):
    r = _run_brm("epic", "create", "demo", "--workflow", "tdd", "--repos", "brm", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    epic_dir = tmp_path / ".brm" / "epics" / "demo"
    assert epic_dir.is_dir()
    assert (epic_dir / "epic.md").is_file()
    assert (epic_dir / "plan.md").is_file()
    assert (epic_dir / "stories").is_dir()


def test_brm_epic_create_writes_valid_frontmatter(tmp_path):
    _run_brm("epic", "create", "demo", "--workflow", "tdd", "--repos", "brm", cwd=tmp_path)
    from lib import epic as _epic
    text = (tmp_path / ".brm" / "epics" / "demo" / "epic.md").read_text()
    e = _epic.parse_epic_text(text)
    assert e.slug == "demo"
    assert e.status == "draft"
    assert e.workflow == "tdd"
    assert e.repos == ["brm"]


def test_brm_epic_create_refuses_duplicate(tmp_path):
    _run_brm("epic", "create", "demo", "--workflow", "tdd", "--repos", "brm", cwd=tmp_path)
    r = _run_brm("epic", "create", "demo", "--workflow", "tdd", "--repos", "brm", cwd=tmp_path)
    assert r.returncode != 0
    assert "exists" in (r.stdout + r.stderr).lower()


def test_brm_epic_create_rejects_traversal_slug(tmp_path):
    r = _run_brm(
        "epic", "create", "../../escaped",
        "--workflow", "tdd", "--repos", "brm",
        cwd=tmp_path,
    )
    assert r.returncode != 0
    # No directories should have been created outside tmp_path/.brm/epics/.
    brm_root = tmp_path / ".brm"
    if brm_root.exists():
        # Only the epics/ container may exist; nothing inside or above it.
        for child in brm_root.rglob("*"):
            assert child == brm_root / "epics", (
                f"traversal created unexpected path: {child}"
            )
    # And nothing escaped above tmp_path.
    assert not (tmp_path.parent / "escaped").exists()
    assert not (tmp_path.parent.parent / "escaped").exists()


def test_find_dispatcher_fallback_loads_brm_script():
    """When neither __main__ nor scripts.brm is in sys.modules, the fallback
    loader must succeed (the file has no `.py` extension, which requires an
    explicit SourceFileLoader)."""
    import importlib
    import sys as _sys
    from lib import epic_cli as _ec

    saved = {}
    for name in ("__main__", "scripts.brm"):
        if name in _sys.modules:
            saved[name] = _sys.modules.pop(name)
    try:
        mod = _ec._find_dispatcher()
        assert hasattr(mod, "register_noun"), (
            "fallback-loaded dispatcher must expose register_noun"
        )
    finally:
        # Restore originals so other tests aren't affected.
        for name, val in saved.items():
            _sys.modules[name] = val


def test_register_is_idempotent_on_reload():
    """Reloading lib.epic_cli must not double-register the `create` verb,
    which would make `_build_parser()` raise ValueError on the duplicate."""
    import importlib
    from lib import epic_cli as _ec

    importlib.reload(_ec)
    dispatcher = _ec._find_dispatcher()
    # Building the parser exercises argparse's subparser registry; a
    # duplicate adder would raise here.
    parser = dispatcher._build_parser()
    assert parser is not None


def test_brm_epic_list_empty(tmp_path):
    (tmp_path / ".brm" / "epics").mkdir(parents=True)
    r = _run_brm("epic", "list", cwd=tmp_path)
    assert r.returncode == 0
    assert "no epics" in r.stdout.lower() or r.stdout.strip() == ""


def test_brm_epic_list_shows_created_epics(tmp_path):
    for slug in ("alpha", "beta"):
        _run_brm("epic", "create", slug, "--workflow", "tdd", "--repos", "brm", cwd=tmp_path)
    r = _run_brm("epic", "list", cwd=tmp_path)
    assert r.returncode == 0
    assert "alpha" in r.stdout
    assert "beta" in r.stdout


def test_brm_epic_list_filters_by_status(tmp_path):
    _run_brm("epic", "create", "alpha", "--workflow", "tdd", "--repos", "brm", cwd=tmp_path)
    r = _run_brm("epic", "list", "--status", "active", cwd=tmp_path)
    assert "alpha" not in r.stdout  # alpha is draft, not active


def test_brm_epic_describe_prints_frontmatter(tmp_path):
    _run_brm("epic", "create", "alpha", "--workflow", "tdd", "--repos", "brm", cwd=tmp_path)
    r = _run_brm("epic", "describe", "alpha", cwd=tmp_path)
    assert r.returncode == 0
    out = r.stdout
    for token in ("alpha", "draft", "tdd", "brm"):
        assert token in out


def test_brm_epic_describe_unknown_slug_errors(tmp_path):
    (tmp_path / ".brm" / "epics").mkdir(parents=True)
    r = _run_brm("epic", "describe", "nope", cwd=tmp_path)
    assert r.returncode != 0
    assert "not found" in (r.stdout + r.stderr).lower()


def test_brm_epic_status_includes_story_rollup(tmp_path):
    _run_brm("epic", "create", "alpha", "--workflow", "tdd", "--repos", "brm", cwd=tmp_path)
    r = _run_brm("epic", "status", "alpha", cwd=tmp_path)
    assert r.returncode == 0
    # No stories yet, so the rollup shows zero stories
    assert "stories" in r.stdout.lower()
    assert "0" in r.stdout


def test_brm_epic_activate_without_approval(tmp_path):
    _run_brm("epic", "create", "alpha", "--workflow", "tdd", "--repos", "brm", cwd=tmp_path)
    r = _run_brm("epic", "activate", "alpha", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    from lib import epic as _epic
    e = _epic.parse_epic_text(
        (tmp_path / ".brm" / "epics" / "alpha" / "epic.md").read_text()
    )
    assert e.status == "active"


def test_brm_epic_activate_with_approval_required_blocks(tmp_path):
    _run_brm("epic", "create", "alpha", "--workflow", "tdd", "--repos", "brm",
             "--require-approval", cwd=tmp_path)
    r = _run_brm("epic", "activate", "alpha", cwd=tmp_path)
    assert r.returncode != 0
    assert "approval" in (r.stdout + r.stderr).lower()


def test_brm_epic_activate_with_approval_passes_when_recorded(tmp_path):
    _run_brm("epic", "create", "alpha", "--workflow", "tdd", "--repos", "brm",
             "--require-approval", cwd=tmp_path)
    # Simulate gate-pass recording (Phase F adds record-gate; for this test we
    # write the approval block directly).
    epic_file = tmp_path / ".brm" / "epics" / "alpha" / "epic.md"
    text = epic_file.read_text().replace(
        "spec_approval:\n  required: true\n",
        "spec_approval:\n  required: true\n  approved_at: 2026-05-19T10:00:00Z\n  approver: keith\n",
    )
    epic_file.write_text(text)
    r = _run_brm("epic", "activate", "alpha", cwd=tmp_path)
    assert r.returncode == 0
