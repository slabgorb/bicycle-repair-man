"""Lint every commands/*.md role brief for required structure."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS = REPO_ROOT / "commands"

REQUIRED_H2_SECTIONS = [
    "## Who you are",
    "## What you do",
    "## What you don't do",
    "## Skills you invoke",
    "## Orchestrator awareness",
    "## Sidecar protocol",
    "## Memory boundary",
    "## Handing off",
]

FORBIDDEN_TOKENS = ("TODO", "TBD", "FIXME", "XXX")

WORD_BUDGET_MAX = 900  # ~1100 tokens; absorbs the orchestrator awareness addendum
WORD_BUDGET_MIN = 200


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


def test_each_brief_has_required_sections_in_order(briefs: list[Path]) -> None:
    for path in briefs:
        text = path.read_text()
        cursor = 0
        for header in REQUIRED_H2_SECTIONS:
            idx = text.find(header, cursor)
            assert idx != -1, f"{path.name}: missing section '{header}' (or out of order)"
            cursor = idx + len(header)


def test_no_forbidden_placeholder_tokens(briefs: list[Path]) -> None:
    for path in briefs:
        text = path.read_text()
        for token in FORBIDDEN_TOKENS:
            assert token not in text, f"{path.name}: contains forbidden token '{token}'"


def test_word_count_within_budget(briefs: list[Path]) -> None:
    for path in briefs:
        text = path.read_text()
        words = len(re.findall(r"\S+", text))
        assert WORD_BUDGET_MIN <= words <= WORD_BUDGET_MAX, (
            f"{path.name}: {words} words outside [{WORD_BUDGET_MIN}, {WORD_BUDGET_MAX}]"
        )


def test_briefs_cover_canonical_roster(briefs: list[Path]) -> None:
    expected = {"tea.md", "dev.md", "reviewer.md", "architect.md", "pm.md", "tech-writer.md"}
    actual = {p.name for p in briefs}
    assert actual == expected, f"roster mismatch: missing {expected - actual}, extra {actual - expected}"
