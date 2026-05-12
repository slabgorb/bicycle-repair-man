"""Shared pytest fixtures for BRM tests."""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to tests/fixtures."""
    return FIXTURES
