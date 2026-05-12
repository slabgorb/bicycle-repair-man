"""Tests for leading-token detection and role mapping."""
from __future__ import annotations

import pytest

from lib import sidecar


# --- extract_command ------------------------------------------------------

@pytest.mark.parametrize(
    "prompt,expected",
    [
        ("/reviewer look at this", "/reviewer"),
        ("/brm:reviewer hello", "/brm:reviewer"),
        ("   /dev hi", "/dev"),
        ("/tech-writer doc the change", "/tech-writer"),
        ("/pm", "/pm"),
        ("", None),
        ("   ", None),
        ("hello /reviewer foo", None),
        ("/", "/"),  # technically a token; role_for_token will return None
    ],
)
def test_extract_command(prompt: str, expected: str | None) -> None:
    assert sidecar.extract_command(prompt) == expected


# --- role_for_token (the exact-match check) -------------------------------

@pytest.mark.parametrize(
    "token,expected",
    [
        ("/reviewer", "reviewer"),
        ("/brm:reviewer", "reviewer"),
        ("/tea", "tea"),
        ("/brm:tea", "tea"),
        ("/dev", "dev"),
        ("/architect", "architect"),
        ("/pm", "pm"),
        ("/tech-writer", "tech-writer"),
        ("/brm:tech-writer", "tech-writer"),
        # Non-matches
        ("/Reviewer", None),         # case-sensitive
        ("/reviewer-fresh", None),   # longer prefix
        ("/reviewers", None),        # plural / longer
        ("/brm:reviewer-fresh", None),
        ("/brm-reviewer", None),     # hyphen not colon
        ("/foo", None),
        ("/", None),
        ("", None),
        ("reviewer", None),          # no leading slash
    ],
)
def test_role_for_token(token: str, expected: str | None) -> None:
    assert sidecar.role_for_token(token) == expected


def test_recognized_tokens_has_twelve() -> None:
    # 6 roles x (bare + namespaced) = 12.
    assert len(sidecar.recognized_tokens()) == 12


def test_recognized_tokens_match_roles() -> None:
    toks = sidecar.recognized_tokens()
    for role in sidecar.ROLES:
        assert f"/{role}" in toks
        assert f"/brm:{role}" in toks
