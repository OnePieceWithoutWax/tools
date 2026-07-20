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
    RECONCILED = "RECONCILED"
    BEHIND = "BEHIND"
    AHEAD = "AHEAD"
    DIRTY = "DIRTY"
    DIVERGED = "DIVERGED"
    CONFLICT = "CONFLICT"
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
    reconcile: bool = False,
    dry_run: bool = False,
) -> RepoResult:
    """Inspect one repository and optionally pull and/or push it, never raising.

    The flags spell every command in the ``-all`` family: ``sync-all`` is the
    default, ``pull-all`` drops ``push``, ``push-all`` drops ``pull``,
    ``fetch-all`` drops both, ``status-all`` drops ``fetch`` as well, and
    ``reconcile-all`` adds ``reconcile``.

    Args:
        path: Repository working directory.
        pull: Fast-forward pull when the repo is strictly behind.
        push: Push when the repo is strictly ahead.
        fetch: Contact the remote first. With False, behind/ahead counts are
            measured against the last-fetched remote-tracking ref and may be
            stale, but nothing touches the network.
        reconcile: Rebase a diverged repo onto its upstream instead of
            reporting DIVERGED, aborting cleanly if the rebase conflicts.
        dry_run: Report what would happen without pulling or pushing.

    Returns:
        A RepoResult describing what happened (or would happen).
    """
    name = path.name
    try:
        return _sync(
            path, name, pull=pull, push=push, fetch=fetch, reconcile=reconcile, dry_run=dry_run
        )
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
    reconcile: bool,
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
        if not reconcile:
            return result(Status.DIVERGED, behind, ahead, "local and upstream have diverged")
        # Rebase rewrites the working tree, so uncommitted work must be reported
        # here rather than falling through to the shared dirty check below.
        if dirty:
            return result(Status.DIRTY, behind, ahead, "uncommitted changes block rebase")
        status, detail = _do_reconcile(path, name, branch, behind, ahead, dry_run)
        return result(status, behind, ahead, detail)

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


def _rebase_in_progress(path: Path) -> bool:
    """Whether a rebase is still half-applied, i.e. the abort did not take.

    Errs towards True: if the git dir cannot even be located, assume the repo
    needs a human rather than reporting a clean abort that may not have happened.
    """
    proc = run_git(path, "rev-parse", "--git-dir")
    if proc.returncode != 0:
        return True
    git_dir = Path(proc.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = path / git_dir
    return (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists()


def _conflict_detail(stdout: str, stderr: str) -> str:
    """Name the files git could not auto-merge, falling back to its error line."""
    files = re.findall(r"Merge conflict in (.+)", stdout)
    if not files:
        return first_line(stderr) or "rebase could not be applied automatically"
    shown = ", ".join(f.strip() for f in files[:3])
    extra = f" (+{len(files) - 3} more)" if len(files) > 3 else ""
    return f"conflicts in: {shown}{extra}"


def _do_reconcile(
    path: Path, name: str, branch: str, behind: int, ahead: int, dry_run: bool
) -> tuple[Status, str]:
    """Rebase a diverged, clean repo onto its upstream and push the result.

    The rebase is the only step that can leave the repo mid-operation, so a
    failure is followed immediately by ``git rebase --abort``, restoring HEAD
    and the working tree to exactly where they were. Nothing is pushed unless
    the whole rebase applied cleanly.

    Returns:
        The resulting status and its detail string.
    """
    if dry_run:
        return Status.RECONCILED, f"dry-run: would rebase {ahead} onto upstream, then push"

    # Upstream was fetched moments ago, so rebasing onto @{u} stays offline and
    # cannot race a second fetch mid-operation.
    rebased = run_git(path, "rebase", "@{u}")
    if rebased.returncode != 0:
        aborted = run_git(path, "rebase", "--abort")
        if aborted.returncode != 0 and _rebase_in_progress(path):
            log.error("rebase stuck", repo=name, error=first_line(aborted.stderr))
            stuck = first_line(aborted.stderr)
            return Status.ERROR, f"left mid-rebase, abort failed: {stuck}"
        detail = _conflict_detail(rebased.stdout, rebased.stderr)
        log.warning("rebase conflicted, aborted", repo=name, detail=detail)
        return Status.CONFLICT, detail

    log.info("rebased", repo=name, branch=branch, onto=behind, replayed=ahead)
    status, detail = _do_push(path, name, branch, ahead, dry_run=False)
    if status is not Status.PUSHED:
        return status, detail
    return Status.RECONCILED, f"rebased {ahead} onto {behind} upstream commit(s), then pushed"


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
