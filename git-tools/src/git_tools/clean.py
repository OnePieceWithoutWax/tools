"""Per-repo branch housekeeping: prune stale remote refs, delete merged branches."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import structlog

from git_tools.gitcmd import current_branch, first_line, run_git

log = structlog.get_logger()


class CleanStatus(StrEnum):
    """Outcome of cleaning a single repository."""

    CLEANED = "CLEANED"
    NOTHING = "NOTHING"
    NO_REMOTE = "NO_REMOTE"
    ERROR = "ERROR"


CLEAN_FAILURE_STATUSES = frozenset({CleanStatus.ERROR})


@dataclass
class CleanResult:
    """Result of cleaning one repository."""

    path: Path
    name: str
    branch: str
    status: CleanStatus
    pruned: int = 0
    deleted: list[str] = field(default_factory=list)
    detail: str = ""


def _default_branch(repo: Path) -> str | None:
    """The remote's default branch (e.g. ``main``), or None if undiscoverable.

    Reads ``refs/remotes/origin/HEAD``, which clones set at clone time. A repo
    whose HEAD ref is missing (common after ``git remote set-head`` was never
    run) yields None rather than a guess — deleting branches against a guessed
    base is not worth the risk.
    """
    proc = run_git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if proc.returncode != 0:
        return None
    ref = proc.stdout.strip()
    return ref.removeprefix("origin/") or None


def _merged_branches(repo: Path, base: str, current: str) -> list[str]:
    """Local branches fully merged into ``origin/base``, excluding base and current.

    Merged-into-*origin* is the safe test: those commits are published, so the
    local branch holds nothing the remote lacks.
    """
    proc = run_git(repo, "branch", "--merged", f"origin/{base}", "--format=%(refname:short)")
    if proc.returncode != 0:
        return []
    names = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return [n for n in names if n not in {base, current}]


def clean_repo(path: Path, *, dry_run: bool = False, prune: bool = True) -> CleanResult:
    """Prune stale remote-tracking refs and delete merged local branches.

    Only ``git branch -d`` is used, never ``-D``: git itself refuses to delete a
    branch holding unmerged commits, so the worst case is a branch left alone.
    The current branch and the remote default branch are never candidates.

    Args:
        path: Repository working directory.
        dry_run: Report what would be pruned/deleted without doing it.
        prune: Contact the remote to prune stale remote-tracking refs. With
            False the whole operation is local and offline.

    Returns:
        A CleanResult describing what happened (or would happen).
    """
    name = path.name
    try:
        return _clean(path, name, dry_run=dry_run, prune=prune)
    except Exception as exc:  # noqa: BLE001 - one repo must not stop the others
        log.error("clean failed", repo=name, error=str(exc))
        return CleanResult(
            path=path, name=name, branch="?", status=CleanStatus.ERROR, detail=str(exc)
        )


def _clean(path: Path, name: str, *, dry_run: bool, prune: bool) -> CleanResult:
    branch = current_branch(path)

    base = _default_branch(path)
    if base is None:
        return CleanResult(
            path=path,
            name=name,
            branch=branch,
            status=CleanStatus.NO_REMOTE,
            detail="no origin/HEAD - cannot tell which branch is the base",
        )

    pruned = 0
    prune_error = ""
    if prune:
        prune_args = ["remote", "prune", "origin"]
        if dry_run:
            prune_args.insert(2, "--dry-run")
        pruned_proc = run_git(path, *prune_args)
        if pruned_proc.returncode != 0:
            # Pruning needs the network; deleting merged branches does not. A
            # dead remote must not cost the repo its local cleanup, so the
            # failure is recorded and the local half still runs. Comparing
            # against a stale origin/<base> only ever deletes fewer branches.
            prune_error = f"prune failed: {first_line(pruned_proc.stderr)}"
            log.warning("prune failed", repo=name, error=prune_error)
        else:
            # git reports pruned refs on stdout or stderr depending on version.
            pruned = sum(
                "[pruned]" in line
                for line in (pruned_proc.stdout + pruned_proc.stderr).splitlines()
            )

    candidates = _merged_branches(path, base, branch)
    deleted: list[str] = []
    failures: list[str] = []
    for candidate in candidates:
        if dry_run:
            deleted.append(candidate)
            continue
        proc = run_git(path, "branch", "-d", candidate)
        if proc.returncode == 0:
            deleted.append(candidate)
        else:
            failures.append(candidate)

    if failures:
        log.warning("branch delete refused", repo=name, branches=failures)
    if deleted and not dry_run:
        log.info("deleted merged branches", repo=name, branches=deleted)

    detail = ""
    if dry_run and (deleted or pruned):
        detail = "dry-run: nothing changed"
    if failures:
        detail = f"git refused to delete: {', '.join(failures[:3])}"
    if prune_error:
        # The prune failure outranks the others: it is the one that needs acting on.
        detail = prune_error

    if prune_error:
        status = CleanStatus.ERROR
    elif deleted or pruned:
        status = CleanStatus.CLEANED
    else:
        status = CleanStatus.NOTHING
    return CleanResult(
        path=path,
        name=name,
        branch=branch,
        status=status,
        pruned=pruned,
        deleted=deleted,
        detail=detail,
    )
