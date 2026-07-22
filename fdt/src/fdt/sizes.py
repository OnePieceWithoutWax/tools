"""Where the space went: folder totals and the largest files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fdt.walk import DEFAULT_SKIP, children, is_real_dir, iter_files, stat_size


@dataclass
class DirSize:
    """A directory's recursive size."""

    path: Path
    depth: int
    size: int
    files: int


@dataclass
class FileSize:
    """One file and its size."""

    path: Path
    size: int


def _measure(
    directory: Path,
    *,
    depth: int,
    max_depth: int,
    skip: frozenset[str],
    out: list[DirSize],
) -> tuple[int, int]:
    """Recursively total ``directory``, appending rows down to ``max_depth``.

    Returns:
        ``(bytes, file_count)`` for the whole subtree, including levels deeper
        than ``max_depth`` -- those are counted, just not listed separately.
    """
    size = 0
    files = 0
    for entry in children(directory):
        if is_real_dir(entry):
            if entry.name in skip:
                continue
            child_size, child_files = _measure(
                entry, depth=depth + 1, max_depth=max_depth, skip=skip, out=out
            )
            size += child_size
            files += child_files
        elif entry.is_file() and not entry.is_symlink():
            size += stat_size(entry)
            files += 1
    if 0 < depth <= max_depth:
        out.append(DirSize(path=directory, depth=depth, size=size, files=files))
    return size, files


def folder_sizes(
    root: Path,
    *,
    depth: int = 1,
    skip: frozenset[str] = DEFAULT_SKIP,
) -> tuple[list[DirSize], int, int]:
    """Total the subdirectories of ``root``.

    Args:
        root: Folder to measure.
        depth: How many levels of subdirectory to list. Deeper folders still
            count toward their ancestors' totals.
        skip: Directory names to leave out entirely.

    Returns:
        ``(rows, total_bytes, total_files)`` with rows largest-first. The
        totals cover everything under ``root``, listed or not.
    """
    rows: list[DirSize] = []
    total_size, total_files = _measure(
        root.resolve(), depth=0, max_depth=depth, skip=skip, out=rows
    )
    rows.sort(key=lambda r: r.size, reverse=True)
    return rows, total_size, total_files


def largest_files(
    root: Path,
    *,
    top: int = 20,
    min_size: int = 0,
    skip: frozenset[str] = DEFAULT_SKIP,
) -> list[FileSize]:
    """The ``top`` largest files under ``root``, at least ``min_size`` bytes."""
    found = [
        FileSize(path=path, size=size)
        for path in iter_files(root.resolve(), skip=skip)
        if (size := stat_size(path)) >= min_size
    ]
    found.sort(key=lambda f: f.size, reverse=True)
    return found[:top]
