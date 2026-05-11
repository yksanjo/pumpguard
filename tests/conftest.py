"""Shared fixtures for PumpGuard tests."""

from __future__ import annotations

import pytest

from pumpguard.memory import Memory


@pytest.fixture
def memory(tmp_path) -> Memory:
    """Fresh SQLite database in a temp directory."""
    return Memory(str(tmp_path / "test.sqlite"))
