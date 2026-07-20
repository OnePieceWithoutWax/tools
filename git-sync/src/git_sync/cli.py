"""Command-line entry point: argument parsing and orchestration."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated

import typer

from git_sync.repo import FAILURE_STATUSES, sync_repo
from git_sync.report import render_table
from git_sync.scanner import find_repos

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.callback()
def callback() -> None:
    """Sync git repositories under a folder: fetch, fast-forward pull, and push clean repos."""


@app.command()
def run(
    folder: Annotated[
        Path | None,
        typer.Argument(
            exists=True,
            file_okay=False,
            help="Folder containing git repositories. Defaults to the current directory.",
        ),
    ] = None,
    recursive: Annotated[
        bool,
        typer.Option("--recursive", "-r", help="Walk the whole tree, not just one level deep."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Report what would happen without making changes."),
    ] = False,
    jobs: Annotated[
        int,
        typer.Option("--jobs", "-j", min=1, help="Number of repos to sync concurrently."),
    ] = 8,
) -> None:
    """Sync every git repo under FOLDER, defaulting to the current directory: fetch, fast-forward
    pull, and push clean repos."""
    target = folder if folder is not None else Path.cwd()
    repos = find_repos(target, recursive=recursive)
    if not repos:
        typer.echo(f"No git repositories found under {target}")
        raise typer.Exit(0)

    # Fetch latency dominates and subprocess releases the GIL, so threads suffice.
    with ThreadPoolExecutor(max_workers=min(jobs, len(repos))) as executor:
        results = list(executor.map(lambda path: sync_repo(path, dry_run=dry_run), repos))

    results.sort(key=lambda r: r.name.lower())
    typer.echo(render_table(results, dry_run=dry_run))

    failed = any(r.status in FAILURE_STATUSES for r in results)
    raise typer.Exit(1 if failed else 0)


def main() -> None:
    """Console-script entry point."""
    app()
