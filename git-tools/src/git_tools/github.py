"""GitHub access via the `gh` CLI, plus the local-vs-GitHub audit.

Everything here shells out to `gh` rather than calling the REST API directly.
That mirrors how the rest of git-tools shells out to `git`, and it means auth,
SSO, enterprise hosts and rate limiting are `gh`'s problem — no token is ever
read, stored, or passed by this tool.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

import structlog
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from git_tools.gitcmd import first_line, run_git

log = structlog.get_logger()

_JSON_FIELDS = "name,nameWithOwner,isFork,isArchived,isPrivate,url,defaultBranchRef,pushedAt"


class GhError(RuntimeError):
    """`gh` is missing, unauthenticated, or returned something unusable."""


class GhRepo(BaseModel):
    """One repository as reported by ``gh repo list --json``."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    name_with_owner: str = Field(alias="nameWithOwner")
    is_fork: bool = Field(alias="isFork", default=False)
    is_archived: bool = Field(alias="isArchived", default=False)
    is_private: bool = Field(alias="isPrivate", default=False)
    url: str = ""
    pushed_at: datetime | None = Field(alias="pushedAt", default=None)
    default_branch_ref: dict[str, str] | None = Field(alias="defaultBranchRef", default=None)

    @property
    def default_branch(self) -> str:
        """The default branch name, or an empty string for an empty repo."""
        return (self.default_branch_ref or {}).get("name", "")


def _run_gh(*args: str, timeout: float = 120.0) -> subprocess.CompletedProcess[str]:
    """Run `gh`, translating a missing binary into a GhError.

    Args:
        *args: Arguments after the `gh` executable.
        timeout: Seconds to wait before giving up.

    Returns:
        The completed process with captured text output.

    Raises:
        GhError: `gh` is not installed or did not finish in time.
    """
    try:
        return subprocess.run(["gh", *args], capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise GhError(
            "the GitHub CLI (`gh`) is required for `hub` commands but was not found on PATH.\n"
            "Install it from https://cli.github.com, then run `gh auth login`."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise GhError(f"`gh {' '.join(args)}` timed out after {timeout:.0f}s") from exc


def list_repos(
    owner: str | None = None,
    *,
    include_forks: bool = False,
    include_archived: bool = False,
    limit: int = 1000,
) -> list[GhRepo]:
    """List repositories visible to the authenticated `gh` user.

    Args:
        owner: User or org to list. Defaults to the authenticated account.
        include_forks: Keep forks in the result.
        include_archived: Keep archived repos in the result.
        limit: Maximum repositories to request from GitHub.

    Returns:
        Repositories sorted by name, case-insensitively.

    Raises:
        GhError: `gh` failed, or returned JSON that did not parse.
    """
    args = ["repo", "list"]
    if owner:
        args.append(owner)
    # Forks/archived are filtered below rather than via gh flags, so one code
    # path handles both; note --limit applies before that filtering.
    args += ["--limit", str(limit), "--json", _JSON_FIELDS]
    proc = _run_gh(*args)
    if proc.returncode != 0:
        raise GhError(f"`gh repo list` failed: {first_line(proc.stderr) or 'unknown error'}")

    try:
        raw = json.loads(proc.stdout or "[]")
        repos = [GhRepo.model_validate(item) for item in raw]
    except (json.JSONDecodeError, ValidationError) as exc:
        raise GhError(f"could not parse `gh repo list` output: {exc}") from exc

    if not include_forks:
        repos = [r for r in repos if not r.is_fork]
    if not include_archived:
        repos = [r for r in repos if not r.is_archived]
    return sorted(repos, key=lambda r: r.name.lower())


def clone_repo(repo: GhRepo, dest: Path) -> tuple[bool, str]:
    """Clone ``repo`` into ``dest``.

    Args:
        repo: Repository to clone.
        dest: Target directory, which must not already exist.

    Returns:
        ``(ok, detail)`` — detail carries git's first error line on failure.
    """
    proc = _run_gh("repo", "clone", repo.name_with_owner, str(dest), timeout=600.0)
    if proc.returncode != 0:
        return False, first_line(proc.stderr) or "clone failed"
    return True, ""


# Matches both remote forms: git@github.com:owner/name.git and
# https://github.com/owner/name(.git)
_REMOTE_RE = re.compile(r"github\.com[:/](?P<owner>[^/]+)/(?P<name>[^/]+?)(?:\.git)?/?$")


def origin_slug(repo_path: Path) -> str | None:
    """The ``owner/name`` an origin remote points at, or None if not GitHub.

    Args:
        repo_path: Local repository working directory.

    Returns:
        The slug, or None when there is no origin or it is not a GitHub URL.
    """
    proc = run_git(repo_path, "remote", "get-url", "origin")
    if proc.returncode != 0:
        return None
    match = _REMOTE_RE.search(proc.stdout.strip())
    return f"{match['owner']}/{match['name']}" if match else None


class AuditStatus(StrEnum):
    """How one repository lines up between GitHub and the local disk."""

    CLONED = "CLONED"
    MISSING = "MISSING"
    ARCHIVED = "ARCHIVED"
    LOCAL_ONLY = "LOCAL_ONLY"
    NO_REMOTE = "NO_REMOTE"


@dataclass
class AuditRow:
    """One line of the audit report."""

    name: str
    status: AuditStatus
    location: str
    detail: str = ""


def audit(local_repos: list[Path], remote_repos: list[GhRepo]) -> list[AuditRow]:
    """Cross-reference local clones against the GitHub repo list.

    Args:
        local_repos: Local repository paths, as found by the scanner.
        remote_repos: Repositories reported by GitHub.

    Returns:
        One row per repository on either side, sorted by name.
    """
    by_slug = {r.name_with_owner.lower(): r for r in remote_repos}
    seen: set[str] = set()
    rows: list[AuditRow] = []

    for path in local_repos:
        slug = origin_slug(path)
        if slug is None:
            rows.append(
                AuditRow(
                    path.name,
                    AuditStatus.NO_REMOTE,
                    str(path),
                    "no origin remote, or origin is not GitHub",
                )
            )
            continue
        remote = by_slug.get(slug.lower())
        if remote is None:
            rows.append(
                AuditRow(
                    path.name,
                    AuditStatus.LOCAL_ONLY,
                    str(path),
                    f"origin {slug} is not in the listed repos",
                )
            )
            continue
        seen.add(slug.lower())
        status = AuditStatus.ARCHIVED if remote.is_archived else AuditStatus.CLONED
        detail = "archived on GitHub but still checked out" if remote.is_archived else ""
        rows.append(AuditRow(remote.name, status, str(path), detail))

    for slug, remote in by_slug.items():
        if slug not in seen:
            rows.append(
                AuditRow(remote.name, AuditStatus.MISSING, remote.url, "on GitHub, not cloned here")
            )

    return sorted(rows, key=lambda r: (r.name.lower(), r.status.value))
