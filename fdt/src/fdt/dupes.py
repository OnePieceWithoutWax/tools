"""Duplicate file detection by content hash."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import structlog

from fdt.walk import DEFAULT_SKIP, iter_files

log = structlog.get_logger()

CHUNK = 1 << 20  # 1 MiB reads: large enough to keep syscalls cheap, small enough to stream
HEAD = 1 << 16  # bytes compared in the cheap first pass


@dataclass
class DupeGroup:
    """Files with identical content."""

    digest: str
    size: int
    paths: list[Path]

    @property
    def wasted(self) -> int:
        """Bytes that would be freed by keeping one copy."""
        return self.size * (len(self.paths) - 1)


def _hash(path: Path, *, limit: int | None = None) -> str | None:
    """blake2b digest of ``path``, or its first ``limit`` bytes. None if unreadable.

    blake2b rather than sha256: this is a same-machine dedupe check, not a
    security boundary, and blake2b is markedly faster on large files.
    """
    digest = hashlib.blake2b(digest_size=16)
    remaining = limit
    try:
        with path.open("rb") as handle:
            while remaining is None or remaining > 0:
                want = CHUNK if remaining is None else min(CHUNK, remaining)
                block = handle.read(want)
                if not block:
                    break
                digest.update(block)
                if remaining is not None:
                    remaining -= len(block)
    except OSError as exc:
        log.warning("could not read file", path=str(path), error=str(exc))
        return None
    return digest.hexdigest()


def _by_size(paths: list[Path], min_size: int) -> dict[int, list[Path]]:
    """Group candidate files by size, dropping unique sizes and tiny files.

    Files of different sizes cannot be duplicates, so this single stat pass
    discards almost everything before any bytes are read.
    """
    groups: dict[int, list[Path]] = {}
    for path in paths:
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size >= min_size:
            groups.setdefault(size, []).append(path)
    return {size: found for size, found in groups.items() if len(found) > 1}


def find_dupes(
    root: Path,
    *,
    min_size: int = 1,
    skip: frozenset[str] = DEFAULT_SKIP,
) -> list[DupeGroup]:
    """Find groups of byte-identical files under ``root``.

    Three passes, cheapest first: size, then the first 64 KiB, then the whole
    file. Only files that survive all three are reported, so a group is a real
    content match rather than a hash-collision guess.

    Args:
        root: Folder to scan.
        min_size: Ignore files smaller than this. The default of 1 skips empty
            files, which are all trivially identical and never interesting.
        skip: Directory names to leave out.

    Returns:
        Groups of two or more identical files, most wasted space first.
    """
    candidates = _by_size(list(iter_files(root.resolve(), skip=skip)), min_size)

    # Second pass: same size and same head. Cheap enough to run on every
    # candidate, and it clears families of files that share only a header.
    narrowed: dict[tuple[int, str], list[Path]] = {}
    for size, paths in candidates.items():
        for path in paths:
            head = _hash(path, limit=HEAD)
            if head is not None:
                narrowed.setdefault((size, head), []).append(path)

    groups: list[DupeGroup] = []
    for (size, _head), paths in narrowed.items():
        if len(paths) < 2:
            continue
        full: dict[str, list[Path]] = {}
        for path in paths:
            digest = _hash(path)
            if digest is not None:
                full.setdefault(digest, []).append(path)
        groups.extend(
            DupeGroup(digest=digest, size=size, paths=sorted(found))
            for digest, found in full.items()
            if len(found) > 1
        )

    groups.sort(key=lambda g: g.wasted, reverse=True)
    return groups
