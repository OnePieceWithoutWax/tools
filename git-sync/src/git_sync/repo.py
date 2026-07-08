"""Per-repo state inspection and sync actions."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import structlog

log = structlog.get_logger()


class Status(StrEnum):
    """Outcome of syncing a single repository."""

    UP_TO_DATE = "UP_TO_DATE"
    PULLED = "PULLED"
    PUSHED = "PUSHED"
    DIRTY = "DIRTY"
    DIVERGED = "DIVERGED"
    NO_UPSTREAM = "NO_UPSTREAM"
    PULL_FAILED = "PULL_FAILED"
    PUSH_FAILED = "PUSH_FAILED"
    ERROR = "ERROR"


FAILURE_STATUSES = frozenset({Status.PULL_FAILED, Status.PUSH_FAILED, Status.ERROR})


@dataclass
class RepoResult:
    """Result of syncing one repository."""

    path: Path
    name: str
    branch: str
    status: Status
    behind: int = 0
    ahead: int = 0
    detail: str = ""


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command in ``repo``.

    Runs plain git with the inherited environment — no ``-c`` credential or
    auth overrides, so per-repo config (includeIf / multi-account HTTPS
    setups) applies as configured. Terminal credential prompts are disabled
    so an unauthenticated repo fails instead of hanging a worker thread.

    Args:
        repo: Repository working directory.
        *args: Git subcommand and arguments.

    Returns:
        The completed process with captured text output; never raises on
        non-zero exit.
    """
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )


def _first_line(text: str) -> str:
    return text.strip().splitlines()[0] if text.strip() else ""


def sync_repo(path: Path, dry_run: bool = False) -> RepoResult:
    """Sync one repository, never raising.

    Args:
        path: Repository working directory.
        dry_run: If True, report what would happen without pulling/pushing.

    Returns:
        A RepoResult describing what happened (or would happen).
    """
    name = path.name
    try:
        return _sync(path, name, dry_run)
    except Exception as exc:  # noqa: BLE001 - one repo must not stop the others
        log.error("sync failed", repo=name, error=str(exc))
        return RepoResult(path=path, name=name, branch="?", status=Status.ERROR, detail=str(exc))


def _sync(path: Path, name: str, dry_run: bool) -> RepoResult:
    branch_proc = _git(path, "rev-parse", "--abbrev-ref", "HEAD")
    branch = branch_proc.stdout.strip() if branch_proc.returncode == 0 else "?"

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

    porcelain = _git(path, "status", "--porcelain")
    if porcelain.returncode != 0:
        return result(Status.ERROR, detail=_first_line(porcelain.stderr))
    if porcelain.stdout.strip():
        return result(Status.DIRTY, detail="working tree has local changes")

    if branch == "HEAD":
        return result(Status.NO_UPSTREAM, detail="detached HEAD")
    upstream = _git(path, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if upstream.returncode != 0:
        return result(Status.NO_UPSTREAM, detail="no upstream configured")

    fetch = _git(path, "fetch")
    if fetch.returncode != 0:
        return result(Status.ERROR, detail=f"fetch failed: {_first_line(fetch.stderr)}")

    counts = _git(path, "rev-list", "--left-right", "--count", "@{u}...HEAD")
    if counts.returncode != 0:
        return result(Status.ERROR, detail=_first_line(counts.stderr))
    behind, ahead = (int(n) for n in counts.stdout.split())

    if behind > 0 and ahead > 0:
        return result(Status.DIVERGED, behind, ahead, "local and upstream have diverged")

    if behind > 0:
        if dry_run:
            return result(Status.PULLED, behind, ahead, "dry-run: would pull --ff-only")
        pull = _git(path, "pull", "--ff-only")
        if pull.returncode != 0:
            log.warning("pull failed", repo=name, error=_first_line(pull.stderr))
            return result(Status.PULL_FAILED, behind, ahead, _first_line(pull.stderr))
        log.info("pulled", repo=name, branch=branch, commits=behind)
        return result(Status.PULLED, behind, ahead)

    if ahead > 0:
        if dry_run:
            return result(Status.PUSHED, behind, ahead, "dry-run: would push")
        push = _git(path, "push")
        if push.returncode != 0:
            log.warning("push failed", repo=name, error=_first_line(push.stderr))
            return result(Status.PUSH_FAILED, behind, ahead, _first_line(push.stderr))
        log.info("pushed", repo=name, branch=branch, commits=ahead)
        return result(Status.PUSHED, behind, ahead)

    return result(Status.UP_TO_DATE)
