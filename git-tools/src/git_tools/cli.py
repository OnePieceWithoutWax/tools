"""Command-line entry point: argument parsing and orchestration.

Naming convention
-----------------
* ``<git-verb>-all`` — a git operation applied once per repository found under
  a folder (``pull-all``, ``push-all``, ``fetch-all``, ``status-all``,
  ``clean-all``, ``config-all``), plus the composites ``sync-all`` and
  ``reconcile-all``, which name an intent rather than a single git verb.
* ``hub <verb>`` — GitHub-specific, via the `gh` CLI. The ``-all`` suffix
  carries the same meaning there, hence ``hub clone-all`` but plain
  ``hub list`` and ``hub audit``, which each run once rather than per repo.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Annotated

import typer

from git_tools.clean import CLEAN_FAILURE_STATUSES, CleanResult, clean_repo
from git_tools.cli_hub import hub_app
from git_tools.gitconfig import CONFIG_FAILURE_STATUSES, ConfigResult, read_config
from git_tools.repo import FAILURE_STATUSES, RepoResult, sync_repo
from git_tools.report import render_table, summarize, truncate
from git_tools.scanner import find_repos

app = typer.Typer(add_completion=False, no_args_is_help=True)
app.add_typer(hub_app, name="hub")

FolderArg = Annotated[
    Path | None,
    typer.Argument(
        exists=True,
        file_okay=False,
        help="Folder containing git repositories. Defaults to the current directory.",
    ),
]
RecursiveOpt = Annotated[
    bool,
    typer.Option("--recursive", "-r", help="Walk the whole tree, not just one level deep."),
]
DryRunOpt = Annotated[
    bool,
    typer.Option("--dry-run", help="Report what would happen without making changes."),
]
JobsOpt = Annotated[
    int,
    typer.Option("--jobs", "-j", min=1, help="Number of repos to process concurrently."),
]


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(_pkg_version("git-tools"))
        raise typer.Exit(0)


@app.callback()
def callback(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the git-tools version and exit.",
        ),
    ] = False,
) -> None:
    """Git housekeeping across many repositories at once."""


def _collect(folder: Path | None, recursive: bool) -> list[Path]:
    """Find repos under ``folder``, exiting cleanly when there are none."""
    target = folder if folder is not None else Path.cwd()
    repos = find_repos(target, recursive=recursive)
    if not repos:
        typer.echo(f"No git repositories found under {target}")
        raise typer.Exit(0)
    return repos


def _in_parallel[T](repos: list[Path], work: Callable[[Path], T], jobs: int) -> list[T]:
    """Run ``work`` over ``repos`` on a thread pool.

    Git subprocesses are I/O-bound and release the GIL, so threads suffice.
    """
    with ThreadPoolExecutor(max_workers=min(jobs, len(repos))) as executor:
        return list(executor.map(work, repos))


def _sync_command(
    folder: Path | None,
    recursive: bool,
    dry_run: bool,
    jobs: int,
    *,
    pull: bool,
    push: bool,
    fetch: bool = True,
    reconcile: bool = False,
) -> None:
    """Shared body of sync-all / pull-all / push-all / fetch-all / status-all / reconcile-all."""
    repos = _collect(folder, recursive)
    results = _in_parallel(
        repos,
        lambda path: sync_repo(
            path, pull=pull, push=push, fetch=fetch, reconcile=reconcile, dry_run=dry_run
        ),
        jobs,
    )
    results.sort(key=lambda r: r.name.lower())
    _emit_sync(results, dry_run=dry_run, fetch=fetch)
    failed = any(r.status in FAILURE_STATUSES for r in results)
    raise typer.Exit(1 if failed else 0)


def _emit_sync(results: Sequence[RepoResult], *, dry_run: bool, fetch: bool) -> None:
    rows = [
        (r.name, r.branch, r.status.value, str(r.behind), str(r.ahead), truncate(r.detail))
        for r in results
    ]
    banner = "(dry-run: no changes made)" if dry_run else None
    if not fetch:
        banner = "(no fetch: counts are from the last fetch and may be stale)"
    typer.echo(
        render_table(
            ("Repo", "Branch", "Status", "Behind", "Ahead", "Detail"),
            rows,
            banner=banner,
            summary=summarize(r.status.value for r in results),
        )
    )


@app.command("sync-all")
def sync_all(
    folder: FolderArg = None,
    recursive: RecursiveOpt = False,
    dry_run: DryRunOpt = False,
    jobs: JobsOpt = 8,
) -> None:
    """Fetch, then pull repos that are behind and push repos that are ahead."""
    _sync_command(folder, recursive, dry_run, jobs, pull=True, push=True)


@app.command("resync-all")
def resync_all(
    folder: FolderArg = None,
    recursive: RecursiveOpt = False,
    dry_run: DryRunOpt = False,
    jobs: JobsOpt = 8,
) -> None:
    """Like sync-all, but also rebases diverged repos onto their upstream, then pushes.

    Everything sync-all does, plus the case it refuses: a repo with both local
    and upstream commits is rebased onto its upstream and pushed. If the rebase
    conflicts it is aborted immediately -- HEAD and the working tree are left
    exactly as they were -- and the repo is reported as CONFLICT for you to
    resolve by hand. Repos with uncommitted changes are never rebased.

    Note that rebasing rewrites your local commits' SHAs. That is harmless for
    the unpushed commits this operates on, but avoid it on a branch someone
    else has already pulled from.
    """
    _sync_command(folder, recursive, dry_run, jobs, pull=True, push=True, reconcile=True)


@app.command("pull-all")
def pull_all(
    folder: FolderArg = None,
    recursive: RecursiveOpt = False,
    dry_run: DryRunOpt = False,
    jobs: JobsOpt = 8,
) -> None:
    """Fetch and fast-forward pull every clean repo that is behind. Never pushes."""
    _sync_command(folder, recursive, dry_run, jobs, pull=True, push=False)


@app.command("push-all")
def push_all(
    folder: FolderArg = None,
    recursive: RecursiveOpt = False,
    dry_run: DryRunOpt = False,
    jobs: JobsOpt = 8,
) -> None:
    """Fetch and push every clean repo that is ahead. Never pulls."""
    _sync_command(folder, recursive, dry_run, jobs, pull=False, push=True)


@app.command("fetch-all")
def fetch_all(
    folder: FolderArg = None,
    recursive: RecursiveOpt = False,
    jobs: JobsOpt = 8,
) -> None:
    """Fetch every repo and report what is behind/ahead. Changes nothing locally."""
    _sync_command(folder, recursive, False, jobs, pull=False, push=False)


@app.command("status-all")
def status_all(
    folder: FolderArg = None,
    recursive: RecursiveOpt = False,
    jobs: JobsOpt = 8,
) -> None:
    """Report each repo's state without touching the network. Fast, offline."""
    _sync_command(folder, recursive, False, jobs, pull=False, push=False, fetch=False)


@app.command("clean-all")
def clean_all(
    folder: FolderArg = None,
    recursive: RecursiveOpt = False,
    dry_run: DryRunOpt = False,
    jobs: JobsOpt = 8,
    prune: Annotated[
        bool,
        typer.Option(
            "--prune/--no-prune",
            help="Contact the remote to prune stale refs. --no-prune stays fully offline.",
        ),
    ] = True,
) -> None:
    """Prune stale remote-tracking refs and delete merged local branches.

    Only branches already merged into the remote's default branch are deleted,
    with `git branch -d`, which refuses anything holding unmerged commits. The
    current branch and the default branch are never touched. A repo whose
    remote is unreachable still gets its local branches cleaned.
    """
    repos = _collect(folder, recursive)
    results: list[CleanResult] = _in_parallel(
        repos, lambda path: clean_repo(path, dry_run=dry_run, prune=prune), jobs
    )
    results.sort(key=lambda r: r.name.lower())

    rows = [
        (
            r.name,
            r.branch,
            r.status.value,
            str(r.pruned),
            truncate(", ".join(r.deleted), 40) or "-",
            truncate(r.detail),
        )
        for r in results
    ]
    typer.echo(
        render_table(
            ("Repo", "Branch", "Status", "Pruned", "Deleted", "Detail"),
            rows,
            banner="(dry-run: no changes made)" if dry_run else None,
            summary=summarize(r.status.value for r in results),
        )
    )
    failed = any(r.status in CLEAN_FAILURE_STATUSES for r in results)
    raise typer.Exit(1 if failed else 0)


@app.command("config-all")
def config_all(
    key: Annotated[str, typer.Argument(help="Git config key to read, e.g. user.email.")],
    folder: FolderArg = None,
    recursive: RecursiveOpt = False,
    expect: Annotated[
        str | None,
        typer.Option(
            "--expect",
            help="Glob the value must match, e.g. '*@gmail.com'. Mismatches exit 1.",
        ),
    ] = None,
) -> None:
    """Read one git config key in every repo, e.g. which identity each commits under."""
    repos = _collect(folder, recursive)
    results: list[ConfigResult] = [read_config(path, key, expect=expect) for path in repos]
    results.sort(key=lambda r: r.name.lower())

    rows = [(r.name, r.value, r.status.value, truncate(r.detail)) for r in results]
    typer.echo(
        render_table(
            ("Repo", key, "Status", "Detail"),
            rows,
            summary=summarize(r.status.value for r in results),
        )
    )
    # Only a stated expectation can be violated; a bare read never fails.
    failed = expect is not None and any(r.status in CONFIG_FAILURE_STATUSES for r in results)
    raise typer.Exit(1 if failed else 0)


def main() -> None:
    """Console-script entry point."""
    app()
