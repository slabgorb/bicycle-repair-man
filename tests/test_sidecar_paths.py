"""Unit tests for lib/sidecar.py."""
from __future__ import annotations

from pathlib import Path

import pytest

from lib import sidecar


# --- find_project_root ----------------------------------------------------

def test_find_project_root_finds_git_dir(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    sub = tmp_path / "a" / "b" / "c"
    sub.mkdir(parents=True)
    assert sidecar.find_project_root(sub) == tmp_path


def test_find_project_root_finds_git_file(tmp_path: Path) -> None:
    # `.git` is a file in submodules / worktree linked checkouts.
    (tmp_path / ".git").write_text("gitdir: /elsewhere\n")
    sub = tmp_path / "x"
    sub.mkdir()
    assert sidecar.find_project_root(sub) == tmp_path


def test_find_project_root_finds_brm_sidecars_dir(tmp_path: Path) -> None:
    (tmp_path / ".brm" / "sidecars").mkdir(parents=True)
    sub = tmp_path / "deep" / "nested"
    sub.mkdir(parents=True)
    assert sidecar.find_project_root(sub) == tmp_path


def test_find_project_root_ignores_bare_brm_without_sidecars(tmp_path: Path) -> None:
    # An orchestrator root has .brm/repos.yaml but no .brm/sidecars/ —
    # find_project_root must NOT match it.
    (tmp_path / ".brm").mkdir()
    (tmp_path / ".brm" / "repos.yaml").write_text("repos: {}\n")
    sub = tmp_path / "deep"
    sub.mkdir()
    assert sidecar.find_project_root(sub) is None


def test_find_project_root_returns_none_when_not_found(tmp_path: Path) -> None:
    # tmp_path has no .git / .brm. Walk hits root with nothing.
    sub = tmp_path / "x"
    sub.mkdir()
    assert sidecar.find_project_root(sub) is None


def test_find_project_root_caps_at_20_levels(tmp_path: Path, monkeypatch) -> None:
    # Build a 25-deep tree with a marker at the root. The cap means we don't
    # find it from the deepest leaf.
    (tmp_path / ".git").mkdir()
    deepest = tmp_path
    for i in range(25):
        deepest = deepest / f"l{i}"
        deepest.mkdir()
    assert sidecar.find_project_root(deepest) is None


def test_find_project_root_returns_cwd_itself_if_marker_present(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert sidecar.find_project_root(tmp_path) == tmp_path


# --- load_sidecar ---------------------------------------------------------

GLOBAL_BODY = "# Reviewer sidecar (global)\n\n## Patterns\n- 2026-01-01 — g1\n"
PROJECT_BODY = "# Reviewer sidecar (project)\n\n## Gotchas\n- 2026-02-01 — p1\n"


def _seed_global(home: Path, role: str, body: str) -> None:
    d = home / ".claude" / "brm" / "sidecars"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{role}.md").write_text(body)


def _seed_project(project_root: Path, role: str, body: str) -> None:
    d = project_root / ".brm" / "sidecars"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{role}.md").write_text(body)


def test_load_sidecar_returns_empty_when_neither_layer(tmp_path: Path) -> None:
    out = sidecar.load_sidecar(
        "reviewer", home=tmp_path / "home", project_root=tmp_path / "proj"
    )
    assert out == ""


def test_load_sidecar_global_only(tmp_path: Path) -> None:
    home = tmp_path / "home"
    proj = tmp_path / "proj"
    proj.mkdir()
    _seed_global(home, "reviewer", GLOBAL_BODY)
    out = sidecar.load_sidecar("reviewer", home=home, project_root=proj)
    assert out.startswith('<brm-sidecar role="reviewer">\n')
    assert '<layer scope="global" path="~/.claude/brm/sidecars/reviewer.md">' in out
    assert GLOBAL_BODY in out
    assert '<layer scope="project"' not in out
    assert out.endswith("</brm-sidecar>\n")


def test_load_sidecar_project_only(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    proj = tmp_path / "proj"
    proj.mkdir()
    _seed_project(proj, "reviewer", PROJECT_BODY)
    out = sidecar.load_sidecar("reviewer", home=home, project_root=proj)
    assert '<layer scope="project" path=".brm/sidecars/reviewer.md">' in out
    assert PROJECT_BODY in out
    assert '<layer scope="global"' not in out


def test_load_sidecar_both_layers_global_first(tmp_path: Path) -> None:
    home = tmp_path / "home"
    proj = tmp_path / "proj"
    proj.mkdir()
    _seed_global(home, "reviewer", GLOBAL_BODY)
    _seed_project(proj, "reviewer", PROJECT_BODY)
    out = sidecar.load_sidecar("reviewer", home=home, project_root=proj)
    g = out.index("global")
    p = out.index("project")
    assert g < p, "global layer must appear before project layer"
    assert GLOBAL_BODY in out
    assert PROJECT_BODY in out


def test_load_sidecar_no_project_root_emits_global_only(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _seed_global(home, "dev", GLOBAL_BODY)
    out = sidecar.load_sidecar("dev", home=home, project_root=None)
    assert '<layer scope="global"' in out
    assert '<layer scope="project"' not in out


def test_load_sidecar_unreadable_layer_skipped(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    proj = tmp_path / "proj"
    proj.mkdir()
    _seed_global(home, "reviewer", GLOBAL_BODY)
    _seed_project(proj, "reviewer", PROJECT_BODY)

    real_read = Path.read_text

    def boom(self, *a, **kw):
        if "global" in str(self) or ".claude/brm" in str(self):
            raise PermissionError("simulated")
        return real_read(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", boom)
    out = sidecar.load_sidecar("reviewer", home=home, project_root=proj)
    # global drops; project survives
    assert '<layer scope="global"' not in out
    assert '<layer scope="project"' in out
    assert PROJECT_BODY in out


def test_load_sidecar_both_unreadable_returns_empty(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    proj = tmp_path / "proj"
    proj.mkdir()
    _seed_global(home, "reviewer", GLOBAL_BODY)
    _seed_project(proj, "reviewer", PROJECT_BODY)
    monkeypatch.setattr(
        Path, "read_text", lambda self, *a, **kw: (_ for _ in ()).throw(OSError("nope"))
    )
    out = sidecar.load_sidecar("reviewer", home=home, project_root=proj)
    assert out == ""


def test_load_sidecar_no_trailing_newline_in_body(tmp_path: Path) -> None:
    """A sidecar file without a trailing newline must still produce
    well-formed XML — the closing </layer> tag belongs on its own line."""
    home = tmp_path / "home"
    proj = tmp_path / "proj"
    proj.mkdir()
    _seed_global(home, "reviewer", "no-trailing-newline-content")
    out = sidecar.load_sidecar("reviewer", home=home, project_root=proj)
    assert "no-trailing-newline-content\n  </layer>" in out
    assert "no-trailing-newline-content  </layer>" not in out


# --- load_sidecar with orchestrator layer --------------------------------

ORCH_BODY = "# Reviewer sidecar (orchestrator)\n\n## Patterns\n- 2026-04-01 — o1\n"


def _seed_orchestrator(orch_root: Path, role: str, body: str) -> None:
    d = orch_root / ".brm" / "sidecars"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{role}.md").write_text(body)


def test_load_sidecar_orchestrator_layer_only(tmp_path: Path) -> None:
    orch = tmp_path / "orch"
    orch.mkdir()
    _seed_orchestrator(orch, "reviewer", ORCH_BODY)
    out = sidecar.load_sidecar(
        "reviewer", home=tmp_path / "home", project_root=None, orchestrator_root=orch
    )
    assert '<layer scope="orchestrator" path=".brm/sidecars/reviewer.md">' in out
    assert ORCH_BODY in out
    assert '<layer scope="global"' not in out
    assert '<layer scope="project"' not in out


def test_load_sidecar_three_layers_global_orch_project(tmp_path: Path) -> None:
    home = tmp_path / "home"
    orch = tmp_path / "orch"
    orch.mkdir()
    proj = orch / "api"
    proj.mkdir()
    _seed_global(home, "reviewer", GLOBAL_BODY)
    _seed_orchestrator(orch, "reviewer", ORCH_BODY)
    _seed_project(proj, "reviewer", PROJECT_BODY)
    out = sidecar.load_sidecar(
        "reviewer", home=home, project_root=proj, orchestrator_root=orch
    )
    g = out.index("scope=\"global\"")
    o = out.index("scope=\"orchestrator\"")
    p = out.index("scope=\"project\"")
    assert g < o < p, f"layer order wrong: g={g}, o={o}, p={p}"
    assert GLOBAL_BODY in out
    assert ORCH_BODY in out
    assert PROJECT_BODY in out


def test_load_sidecar_orchestrator_arg_none_acts_like_v0_1(tmp_path: Path) -> None:
    home = tmp_path / "home"
    proj = tmp_path / "proj"
    proj.mkdir()
    _seed_global(home, "reviewer", GLOBAL_BODY)
    _seed_project(proj, "reviewer", PROJECT_BODY)
    out_v01 = sidecar.load_sidecar("reviewer", home=home, project_root=proj)
    out_v02 = sidecar.load_sidecar(
        "reviewer", home=home, project_root=proj, orchestrator_root=None
    )
    assert out_v01 == out_v02


def test_load_sidecar_orch_unreadable_skipped(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    orch = tmp_path / "orch"
    orch.mkdir()
    proj = orch / "p"
    proj.mkdir()
    _seed_global(home, "reviewer", GLOBAL_BODY)
    _seed_orchestrator(orch, "reviewer", ORCH_BODY)
    _seed_project(proj, "reviewer", PROJECT_BODY)

    real_read = Path.read_text

    def boom(self, *a, **kw):
        if "/orch/.brm/sidecars" in str(self):
            raise PermissionError("simulated")
        return real_read(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", boom)
    out = sidecar.load_sidecar(
        "reviewer", home=home, project_root=proj, orchestrator_root=orch
    )
    assert '<layer scope="orchestrator"' not in out
    assert '<layer scope="global"' in out
    assert '<layer scope="project"' in out
