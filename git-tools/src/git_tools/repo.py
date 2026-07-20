"""Per-repo state inspection and pull/push actions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import structlog

from git_tools.gitcmd import current_branch, first_line, run_git

log = structlog.get_logger()


class Status(StrEnum):
    """Outcome of inspecting or syncing a single repository."""

    UP_TO_DATE = "UP_TO_DATE"
    PULLED = "PULLED"
    PUSHED = "PUSHED"
    BEHIND = "BEHIND"
    AHEAD = "AHEAD"
    DIRTY = "DIRTY"
    DIVERGED = "DIVERGED"
    NO_UPSTREAM = "NO_UPSTREAM"
    COLLISION = "COLLISION"
    PULL_FAILED = "PULL_FAILED"
    PUSH_FAILED = "PUSH_FAILED"
    ERROR = "ERROR"


FAILURE_STATUSES = frozenset({Status.PULL_FAILED, Status.PUSH_FAILED, Status.ERROR})


@dataclass
class RepoResult:
    """Result of inspecting or syncing one repository."""

    path: Path
    name: str
    branch: str
    status: Status
    behind: int = 0
    ahead: int = 0
    detail: str = ""


# Untracked files do not block the sync, so a pull can land on one: git refuses
# rather than clobber it. It aborts before touching the index or working tree,
# so there is nothing to undo — the repo is simply left as it was.
_COLLISION_MARKER = "untracked working tree file"


def _collision_paths(stderr: str) -> list[str]:
    """Untracked paths git named as blocking a pull, best-effort.

    Git lists them tab-indented under its error line when there are several, and
    inline in quotes when there is one.

    Args:
        stderr: Captured stderr from the failed pull.

    Returns:
        The colliding paths, or an empty list if none could be parsed.
    """
    listed = [line.strip() for line in stderr.splitlines() if line.startswith("\t")]
    if listed:
        return listed
    quoted = re.search(r"'([^']+)'", stderr)
    return [quoted.group(1)] if quoted else []


def _collision_detail(paths: list[str]) -> str:
    """Summarise colliding paths for one table cell, keeping the row short."""
    if not paths:
        return "untracked files would be overwritten by pull"
    shown = ", ".join(paths[:3])
    extra = f" (+{len(paths) - 3} more)" if len(paths) > 3 else ""
    return f"untracked file(s) block pull: {shown}{extra}"


def sync_repo(
    path: Path,
    *,
    pull: bool = True,
    push: bool = True,
    fetch: bool = True,
    dry_run: bool = False,
) -> RepoResult:
    """Inspect one repository and optionally pull and/or push it, never raising.

    The four flags spell every command in the ``-all`` family: ``sync-all`` is
    the default, ``pull-all`` drops ``push``, ``push-all`` drops ``pull``,
    ``fetch-all`` drops both, and ``status-all`` drops ``fetch`` as well.

    Args:
        path: Repository working directory.
        pull: Fast-forward pull when the repo is strictly behind.
        push: Push when the repo is strictly ahead.
        fetch: Contact the remote first. With False, behind/ahead counts are
            measured against the last-fetched remote-tracking ref and may be
            stale, but nothing touches the network.
        dry_run: Report what would happen without pulling or pushing.

    Returns:
        A RepoResult describing what happened (or would happen).
    """
    name = path.name
    try:
        return _sync(path, name, pull=pull, push=push, fetch=fetch, dry_run=dry_run)
    except Exception as exc:  # noqa: BLE001 - one repo must not stop the others
        log.error("sync failed", repo=name, error=str(exc))
        return RepoResult(path=path, name=name, branch="?", status=Status.ERROR, detail=str(exc))


def _sync(
    path: Path,
    name: str,
    *,
    pull: bool,
    push: bool,
    fetch: bool,
    dry_run: bool,
) -> RepoResult:
    branch = current_branch(path)

    def result(status: Status, behind: int = 0, ahead: int = 0, detail: str = "") -> RepoResult:
        return RepoResult(
            path=path,
            name=name,
            branch=branch,
            status=status,
            behind=behind,
            ahead=ahead,
            detail=detail,
        )

    # Untracked files are ignored: build artefacts and scratch files are no reason
    # to skip a repo, and a pull can only be harmed by one via a name collision,
    # which git catches for us (see Status.COLLISION).
    porcelain = run_git(path, "status", "--porcelain=v1", "--untracked-files=no")
    if porcelain.returncode != 0:
        return result(Status.ERROR, detail=first_line(porcelain.stderr))
    dirty = bool(porcelain.stdout.strip())

    if branch == "HEAD":
        return result(Status.NO_UPSTREAM, detail="detached HEAD")
    upstream = run_git(path, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if upstream.returncode != 0:
        return result(Status.NO_UPSTREAM, detail="no upstream configured")

    if fetch:
        fetched = run_git(path, "fetch")
        if fetched.returncode != 0:
            return result(Status.ERROR, detail=f"fetch failed: {first_line(fetched.stderr)}")

    counts = run_git(path, "rev-list", "--left-right", "--count", "@{u}...HEAD")
    if counts.returncode != 0:
        return result(Status.ERROR, detail=first_line(counts.stderr))
    behind, ahead = (int(n) for n in counts.stdout.split())

    if behind > 0 and ahead > 0:
        return result(Status.DIVERGED, behind, ahead, "local and upstream have diverged")

    # A dirty repo is reported with its counts, but never pulled or pushed.
    if dirty:
        return result(Status.DIRTY, behind, ahead, "tracked files have uncommitted changes")

    if behind > 0:
        if not pull:
            return result(Status.BEHIND, behind, ahead)
        status, detail = _do_pull(path, name, branch, behind, dry_run)
        return result(status, behind, ahead, detail)

    if ahead > 0:
        if not push:
            return result(Status.AHEAD, behind, ahead)
        status, detail = _do_push(path, name, branch, ahead, dry_run)
        return result(status, behind, ahead, detail)

    return result(Status.UP_TO_DATE)


def _do_pull(path: Path, name: str, branch: str, behind: int, dry_run: bool) -> tuple[Status, str]:
    """Fast-forward pull a repo known to be strictly behind and clean.

    Returns:
        The resulting status and its detail string.
    """
    if dry_run:
        return Status.PULLED, "dry-run: would pull --ff-only"
    pulled = run_git(path, "pull", "--ff-only")
    if pulled.returncode != 0:
        if _COLLISION_MARKER in pulled.stderr.lower():
            paths = _collision_paths(pulled.stderr)
            log.warning("pull blocked by untracked files", repo=name, files=paths)
            return Status.COLLISION, _collision_detail(paths)
        log.warning("pull failed", repo=name, error=first_line(pulled.stderr))
        return Status.PULL_FAILED, first_line(pulled.stderr)
    log.info("pulled", repo=name, branch=branch, commits=behind)
    return Status.PULLED, ""


def _do_push(path: Path, name: str, branch: str, ahead: int, dry_run: bool) -> tuple[Status, str]:
    """Push a repo known to be strictly ahead and clean.

    Returns:
        The resulting status and its detail string.
    """
    if dry_run:
        return Status.PUSHED, "dry-run: would push"
    pushed = run_git(path, "push")
    if pushed.returncode != 0:
        log.warning("push failed", repo=name, error=first_line(pushed.stderr))
        return Status.PUSH_FAILED, first_line(pushed.stderr)
    log.info("pushed", repo=name, branch=branch, commits=ahead)
    return Status.PUSHED, ""
