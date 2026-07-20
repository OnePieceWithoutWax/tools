"""Find git repositories under a folder."""

from __future__ import annotations

from pathlib import Path


def _is_repo(directory: Path) -> bool:
    # .git may be a file (worktrees, submodules), not only a directory
    return (directory / ".git").exists()


def find_repos(root: Path, recursive: bool = False) -> list[Path]:
    """Find git repositories under ``root``.

    If ``root`` itself is a repository it is the sole result. Otherwise the
    immediate subdirectories are checked; with ``recursive`` the whole tree
    is walked, without descending into repositories already found.

    Args:
        root: Folder to scan.
        recursive: Walk the full tree instead of one level deep.

    Returns:
        Repository paths in depth-first, name-sorted traversal order.
    """
    root = root.resolve()
    if _is_repo(root):
        return [root]

    repos: list[Path] = []

    def scan(directory: Path, deeper: bool) -> None:
        try:
            children = sorted(p for p in directory.iterdir() if p.is_dir())
        except OSError:
            return  # unreadable directory — skip, don't abort the scan
        for child in children:
            if child.name == ".git":
                continue
            if _is_repo(child):
                repos.append(child)
            elif deeper:
                scan(child, deeper)

    scan(root, deeper=recursive)
    return repos
