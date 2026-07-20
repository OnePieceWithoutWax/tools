"""The `hub` sub-app: GitHub-specific commands, backed by the `gh` CLI."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated

import typer

from git_tools.github import AuditStatus, GhError, GhRepo, audit, clone_repo, list_repos
from git_tools.report import render_table, summarize, truncate
from git_tools.scanner import find_repos

hub_app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="GitHub commands, via the `gh` CLI (install from https://cli.github.com).",
)

OwnerOpt = Annotated[
    str | None,
    typer.Option("--owner", help="User or org to list. Defaults to the `gh` account."),
]
ForksOpt = Annotated[bool, typer.Option("--forks", help="Include forks.")]
ArchivedOpt = Annotated[bool, typer.Option("--archived", help="Include archived repos.")]
LimitOpt = Annotated[
    int, typer.Option("--limit", min=1, help="Maximum repos to request from GitHub.")
]


def _fetch(owner: str | None, forks: bool, archived: bool, limit: int) -> list[GhRepo]:
    """List repos, turning a GhError into a clean CLI failure."""
    try:
        return list_repos(owner, include_forks=forks, include_archived=archived, limit=limit)
    except GhError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc


@hub_app.command("list")
def list_command(
    owner: OwnerOpt = None,
    forks: ForksOpt = False,
    archived: ArchivedOpt = False,
    limit: LimitOpt = 1000,
) -> None:
    """List your GitHub repositories."""
    repos = _fetch(owner, forks, archived, limit)
    if not repos:
        typer.echo("No repositories found.")
        raise typer.Exit(0)

    rows = [
        (
            r.name_with_owner,
            "private" if r.is_private else "public",
            r.default_branch or "-",
            r.pushed_at.date().isoformat() if r.pushed_at else "-",
            " ".join(tag for tag, on in (("fork", r.is_fork), ("archived", r.is_archived)) if on),
        )
        for r in repos
    ]
    typer.echo(
        render_table(
            ("Repo", "Visibility", "Default", "Last push", "Flags"),
            rows,
            summary=f"{len(repos)} repo(s)",
        )
    )


@hub_app.command("clone-all")
def clone_all(
    dest: Annotated[
        Path | None,
        typer.Argument(
            file_okay=False,
            help="Directory to clone into. Defaults to the current directory.",
        ),
    ] = None,
    owner: OwnerOpt = None,
    forks: ForksOpt = False,
    archived: ArchivedOpt = False,
    limit: LimitOpt = 1000,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="List what would be cloned, and clone nothing.")
    ] = False,
    jobs: Annotated[
        int, typer.Option("--jobs", "-j", min=1, help="Number of clones to run concurrently.")
    ] = 8,
) -> None:
    """Clone every one of your GitHub repos that is not already here.

    Forks and archived repos are skipped unless asked for. An existing
    directory of the same name is left completely alone.
    """
    target = (dest if dest is not None else Path.cwd()).resolve()
    repos = _fetch(owner, forks, archived, limit)
    if not repos:
        typer.echo("No repositories found.")
        raise typer.Exit(0)

    target.mkdir(parents=True, exist_ok=True)

    def work(repo: GhRepo) -> tuple[str, str, str]:
        destination = target / repo.name
        if destination.exists():
            return repo.name_with_owner, "SKIPPED", "already present"
        if dry_run:
            return repo.name_with_owner, "CLONED", f"dry-run: would clone into {destination.name}"
        ok, detail = clone_repo(repo, destination)
        return repo.name_with_owner, "CLONED" if ok else "FAILED", detail

    with ThreadPoolExecutor(max_workers=min(jobs, len(repos))) as executor:
        results = list(executor.map(work, repos))

    rows = [(name, status, truncate(detail)) for name, status, detail in results]
    typer.echo(
        render_table(
            ("Repo", "Status", "Detail"),
            rows,
            banner="(dry-run: nothing cloned)" if dry_run else None,
            summary=summarize(status for _, status, _ in results),
        )
    )
    raise typer.Exit(1 if any(status == "FAILED" for _, status, _ in results) else 0)


@hub_app.command("audit")
def audit_command(
    folder: Annotated[
        Path | None,
        typer.Argument(
            exists=True,
            file_okay=False,
            help="Folder holding your clones. Defaults to the current directory.",
        ),
    ] = None,
    recursive: Annotated[
        bool, typer.Option("--recursive", "-r", help="Walk the whole tree, not just one level.")
    ] = False,
    owner: OwnerOpt = None,
    forks: ForksOpt = False,
    archived: ArchivedOpt = True,
    limit: LimitOpt = 1000,
) -> None:
    """Cross-reference local clones against GitHub: what is missing, what is unbacked.

    Archived repos are included by default here, since a local checkout of one
    is exactly the kind of thing worth knowing about.
    """
    target = (folder if folder is not None else Path.cwd()).resolve()
    local = find_repos(target, recursive=recursive)
    remote = _fetch(owner, forks, archived, limit)

    rows_data = audit(local, remote)
    rows = [
        (r.name, r.status.value, truncate(r.location, 50), truncate(r.detail)) for r in rows_data
    ]
    typer.echo(
        render_table(
            ("Repo", "Status", "Where", "Detail"),
            rows,
            summary=summarize(r.status.value for r in rows_data),
        )
    )
    typer.echo(
        "\nCLONED = on GitHub and here | MISSING = on GitHub, not cloned"
        "\nLOCAL_ONLY = here, not in the listed GitHub repos"
        f" | NO_REMOTE = no GitHub origin | {AuditStatus.ARCHIVED.value} = archived upstream"
    )
