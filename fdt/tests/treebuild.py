"""Helper for building throwaway directory trees.

Deliberately not named ``conftest``: pytest imports every ``conftest.py`` in
the workspace under the same module name, so a test importing symbols from one
would collide with another member's.
"""

from __future__ import annotations

from pathlib import Path


def make_tree(root: Path, layout: dict[str, str | None]) -> None:
    """Create a tree from a ``{relative path: contents}`` mapping.

    A value of None means "directory"; a string means "file with this text".
    Parent directories are created as needed.
    """
    for relative, contents in layout.items():
        target = root / relative
        if contents is None:
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents, encoding="utf-8")
