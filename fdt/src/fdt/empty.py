"""Removal of empty directories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import structlog

from fdt.results import Status
from fdt.walk import DEFAULT_SKIP, children, is_real_dir

log = structlog.get_logger()

# Zero-value files that Windows and macOS scatter through folders. Not ignored
# by default -- deleting them is a real deletion, so it stays opt-in.
JUNK_NAMES = frozenset({"thumbs.db", "desktop.ini", ".ds_store"})


@dataclass
class EmptyResult:
    """One directory that was (or would be) removed, or failed to be."""

    path: Path
    status: Status
    removed_files: list[str]
    detail: str = ""


def _ignorable(entry: Path, ignore: frozenset[str]) -> bool:
    """True for a file the caller asked to treat as if it were not there."""
    return bool(ignore) and entry.name.lower() in ignore and entry.is_file()


def _leaf_is_empty(directory: Path, ignore: frozenset[str]) -> bool:
    """True when ``directory`` holds nothing but ignorable files."""
    return all(_ignorable(entry, ignore) for entry in children(directory))


def _delete(
    directory: Path,
    *,
    dry_run: bool,
    ignore: frozenset[str],
    results: list[EmptyResult],
) -> bool:
    """Remove ``directory`` (and any ignorable files in it). True if it is gone.

    A failure is recorded as an ERROR row and reported as "not gone", so the
    parent correctly stops considering itself empty.
    """
    removed = [e.name for e in children(directory) if _ignorable(e, ignore)]
    if dry_run:
        results.append(EmptyResult(directory, Status.WOULD_DELETE, removed))
        return True
    try:
        for entry in children(directory):
            if _ignorable(entry, ignore):
                entry.unlink()
        directory.rmdir()
    except OSError as exc:
        log.warning("could not remove directory", path=str(directory), error=str(exc))
        results.append(EmptyResult(directory, Status.ERROR, [], str(exc)))
        return False
    results.append(EmptyResult(directory, Status.DELETED, removed))
    return True


def _visit(
    directory: Path,
    *,
    recursive: bool,
    dry_run: bool,
    ignore: frozenset[str],
    skip: frozenset[str],
    results: list[EmptyResult],
) -> bool:
    """Process the contents of ``directory``; return True if it ends up empty.

    Depth-first and bottom-up, so a folder whose only contents are empty
    folders collapses in a single pass -- and a folder whose child could not be
    removed is correctly left alone.
    """
    empty = True
    for entry in children(directory):
        if is_real_dir(entry):
            if entry.name in skip:
                empty = False
                continue
            child_empty = (
                _visit(
                    entry,
                    recursive=recursive,
                    dry_run=dry_run,
                    ignore=ignore,
                    skip=skip,
                    results=results,
                )
                if recursive
                else _leaf_is_empty(entry, ignore)
            )
            if child_empty and _delete(entry, dry_run=dry_run, ignore=ignore, results=results):
                continue
            empty = False
        elif not _ignorable(entry, ignore):
            # Symlinks and junctions land here: never followed, always content.
            empty = False
    return empty


def clean_empty(
    root: Path,
    *,
    recursive: bool = False,
    dry_run: bool = False,
    ignore: frozenset[str] = frozenset(),
    skip: frozenset[str] = DEFAULT_SKIP,
) -> list[EmptyResult]:
    """Delete empty directories under ``root``.

    ``root`` itself is never deleted, however empty it ends up. Symlinks and
    junctions are treated as content and never followed, so nothing outside
    ``root`` can be reached.

    Args:
        root: Folder to clean.
        recursive: Walk the whole tree bottom-up, so a folder that becomes
            empty once its empty children go is removed too. Without it, only
            the immediate subdirectories of ``root`` are considered.
        dry_run: Report what would be removed without removing it.
        ignore: Lowercased file names to treat as absent when deciding whether
            a folder is empty. Such files are deleted along with their folder.
        skip: Directory names never descended into or deleted.

    Returns:
        One result per directory removed, would-be removed, or failed --
        children before parents.
    """
    root = root.resolve()
    results: list[EmptyResult] = []
    _visit(root, recursive=recursive, dry_run=dry_run, ignore=ignore, skip=skip, results=results)
    return results
