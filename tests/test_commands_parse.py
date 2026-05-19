"""Lint every commands/*.md role brief for required structure."""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS = REPO_ROOT / "commands"

FORBIDDEN_TOKENS = ("TODO", "TBD", "FIXME", "XXX")


@pytest.fixture(scope="module")
def briefs() -> list[Path]:
    paths = sorted(COMMANDS.glob("*.md"))
    assert len(paths) == 6, f"expected 6 role briefs, found {len(paths)}: {paths}"
    return paths


def _frontmatter(text: str) -> dict[str, str] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    body = text[4:end]
    out: dict[str, str] = {}
    for line in body.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip()
    return out


def test_each_brief_has_description_frontmatter(briefs: list[Path]) -> None:
    for path in briefs:
        text = path.read_text()
        fm = _frontmatter(text)
        assert fm is not None, f"{path.name}: no frontmatter"
        assert fm.get("description"), f"{path.name}: no description"


def test_each_brief_has_brm_role_frontmatter(briefs: list[Path]) -> None:
    """Commands must declare brm-role: true and brm-agent: <name> since v0.4 migration."""
    for path in briefs:
        text = path.read_text()
        fm = _frontmatter(text)
        assert fm is not None, f"{path.name}: no frontmatter"
        assert fm.get("brm-role") == "true", f"{path.name}: missing brm-role: true"
        assert fm.get("brm-agent"), f"{path.name}: missing brm-agent:"


def test_each_brief_body_is_thin(briefs: list[Path]) -> None:
    """Wrapper body should be small — role content lives in agents/."""
    for path in briefs:
        text = path.read_text()
        body = text.split("---", 2)[-1] if text.startswith("---") else text
        assert len(body.splitlines()) < 50, f"{path.name}: wrapper body should be thin (< 50 lines)"


def test_no_forbidden_placeholder_tokens(briefs: list[Path]) -> None:
    for path in briefs:
        text = path.read_text()
        for token in FORBIDDEN_TOKENS:
            assert token not in text, f"{path.name}: contains forbidden token '{token}'"


def test_briefs_cover_canonical_roster(briefs: list[Path]) -> None:
    expected = {"tea.md", "dev.md", "reviewer.md", "architect.md", "pm.md", "tech-writer.md"}
    actual = {p.name for p in briefs}
    assert actual == expected, f"roster mismatch: missing {expected - actual}, extra {actual - expected}"
