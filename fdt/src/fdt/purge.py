"""Removal of directories by name, contents and all.

Unlike :mod:`fdt.empty`, this deletes folders that hold files -- so it only
ever acts on names the caller named explicitly.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import structlog

from fdt.results import Status
from fdt.walk import DEFAULT_SKIP, children, is_real_dir, iter_files, stat_size

log = structlog.get_logger()

JUPYTER_CHECKPOINTS = ".ipynb_checkpoints"


@dataclass
class PurgeResult:
    """One directory that was (or would be) removed, or failed to be."""

    path: Path
    status: Status
    files: int
    size: int
    detail: str = ""


def _weigh(directory: Path) -> tuple[int, int]:
    """``(file_count, bytes)`` held by ``directory``, for the report."""
    sizes = [stat_size(path) for path in iter_files(directory, skip=frozenset())]
    return len(sizes), sum(sizes)


def _remove(directory: Path, *, dry_run: bool) -> PurgeResult:
    """Delete ``directory`` and everything in it."""
    count, size = _weigh(directory)
    if dry_run:
        return PurgeResult(directory, Status.WOULD_DELETE, count, size)
    try:
        shutil.rmtree(directory)
    except OSError as exc:
        log.warning("could not remove directory", path=str(directory), error=str(exc))
        return PurgeResult(directory, Status.ERROR, count, size, str(exc))
    log.info("removed directory", path=str(directory), files=count)
    return PurgeResult(directory, Status.DELETED, count, size)


def purge_dirs(
    root: Path,
    names: frozenset[str],
    *,
    recursive: bool = False,
    dry_run: bool = False,
    skip: frozenset[str] = DEFAULT_SKIP,
) -> list[PurgeResult]:
    """Delete every directory named in ``names`` under ``root``, contents included.

    Args:
        root: Folder to search. A matching directory sitting directly in
            ``root`` is removed whether or not ``recursive`` is set.
        names: Directory names to remove, matched exactly.
        recursive: Search the whole tree rather than only ``root`` itself.
        dry_run: Report what would be removed without removing it.
        skip: Directory names never descended into.

    Returns:
        One result per matching directory, in depth-first traversal order.
    """
    results: list[PurgeResult] = []
    stack = [root.resolve()]
    while stack:
        directory = stack.pop()
        for entry in children(directory):
            if not is_real_dir(entry):
                continue
            if entry.name in names:
                results.append(_remove(entry, dry_run=dry_run))
            elif recursive and entry.name not in skip:
                stack.append(entry)
    return results
