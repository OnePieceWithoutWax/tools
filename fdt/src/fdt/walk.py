"""Filesystem traversal shared by every command.

Every walk here is link-safe: symlinks and Windows junctions are reported but
never descended into. Following them risks unbounded loops and, worse, lets an
operation escape the folder the user pointed at.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

# Directories that are almost never the subject of a housekeeping run and are
# expensive to walk. Overridable per command via --no-skip-default.
DEFAULT_SKIP = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
    }
)


def is_real_dir(path: Path) -> bool:
    """True for a directory that is not a symlink or Windows junction.

    ``Path.is_dir()`` follows links, so it alone would let a walk step outside
    the tree being processed.
    """
    try:
        return path.is_dir() and not path.is_symlink() and not path.is_junction()
    except OSError:
        return False


def stat_size(path: Path) -> int:
    """Size of ``path`` in bytes, or 0 if it cannot be stat'd."""
    try:
        return path.stat().st_size
    except OSError:
        return 0


def children(directory: Path) -> list[Path]:
    """Entries of ``directory``, sorted by name; empty when unreadable.

    An unreadable folder (permissions, a device that went away) must not abort
    a whole run, so the error is swallowed here and the caller sees no entries.
    """
    try:
        return sorted(directory.iterdir())
    except OSError:
        return []


def subdirs(directory: Path, skip: frozenset[str] = DEFAULT_SKIP) -> list[Path]:
    """Immediate real subdirectories of ``directory``, minus skipped names."""
    return [p for p in children(directory) if is_real_dir(p) and p.name not in skip]


def iter_files(root: Path, skip: frozenset[str] = DEFAULT_SKIP) -> Iterator[Path]:
    """Yield every regular file under ``root``, depth-first, without following links.

    Args:
        root: Folder to walk.
        skip: Directory names not to descend into.

    Yields:
        Paths of regular files (symlinked files are skipped -- hashing or
        sizing them would double-count their target).
    """
    stack = [root]
    while stack:
        directory = stack.pop()
        for entry in children(directory):
            if is_real_dir(entry):
                if entry.name not in skip:
                    stack.append(entry)
            elif entry.is_file() and not entry.is_symlink():
                yield entry
