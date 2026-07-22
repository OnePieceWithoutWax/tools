"""Shared fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """An empty temporary folder to build a tree in."""
    root = tmp_path / "root"
    root.mkdir()
    return root
