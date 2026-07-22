"""The ``fdt folder`` sub-app: commands that act on directories."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from fdt.empty import JUNK_NAMES, clean_empty
from fdt.options import DryRunOpt, NoDefaultSkipsOpt, PathArg, RecursiveOpt, resolve_skip
from fdt.purge import JUPYTER_CHECKPOINTS, purge_dirs
from fdt.report import human_bytes, render_table, summarize, truncate
from fdt.results import FAILURE_STATUSES, Status
from fdt.sizes import folder_sizes

folder_app = typer.Typer(add_completion=False, no_args_is_help=True, help="Directory commands.")


@folder_app.command("clean-empty")
def clean_empty_cmd(
    path: PathArg = None,
    recursive: RecursiveOpt = False,
    dry_run: DryRunOpt = False,
    include_junk: Annotated[
        bool,
        typer.Option(
            "--include-junk",
            help="Treat Thumbs.db / desktop.ini / .DS_Store as absent, and delete them too.",
        ),
    ] = False,
    ignore: Annotated[
        list[str] | None,
        typer.Option(
            "--ignore",
            help="File name to treat as absent when deciding emptiness. Repeatable.",
        ),
    ] = None,
    no_default_skips: NoDefaultSkipsOpt = False,
) -> None:
    """Delete empty folders under PATH (default: the current directory).

    Without --recursive only the immediate subfolders are considered. With it
    the tree is walked bottom-up, so a folder holding nothing but empty folders
    collapses entirely in one pass.

    PATH itself is never deleted, and symlinks and junctions are treated as
    content rather than followed -- nothing outside PATH can be reached.
    """
    target = path if path is not None else Path.cwd()
    ignored = {name.lower() for name in (ignore or [])}
    if include_junk:
        ignored |= JUNK_NAMES

    results = clean_empty(
        target,
        recursive=recursive,
        dry_run=dry_run,
        ignore=frozenset(ignored),
        skip=resolve_skip(no_default_skips),
    )
    if not results:
        typer.echo(f"No empty folders under {target}")
        raise typer.Exit(0)

    rows = [
        (
            truncate(str(r.path.relative_to(target.resolve()))),
            r.status.value,
            truncate(", ".join(r.removed_files), 30) or "-",
            truncate(r.detail),
        )
        for r in results
    ]
    typer.echo(
        render_table(
            ("Folder", "Status", "Files removed", "Detail"),
            rows,
            banner="(dry-run: nothing was deleted)" if dry_run else None,
            summary=summarize(r.status.value for r in results),
        )
    )
    failed = any(r.status in FAILURE_STATUSES for r in results)
    raise typer.Exit(1 if failed else 0)


@folder_app.command("clean-jupyter")
def clean_jupyter_cmd(
    path: PathArg = None,
    recursive: RecursiveOpt = False,
    dry_run: DryRunOpt = False,
    no_default_skips: NoDefaultSkipsOpt = False,
) -> None:
    """Delete .ipynb_checkpoints folders under PATH (default: the current directory).

    Unlike clean-empty this removes the folders whole, checkpoint notebooks
    included -- that is the point of them: Jupyter recreates the folder on the
    next save, and the checkpoints are copies of notebooks you still have.

    Without --recursive only a checkpoints folder sitting directly in PATH is
    removed; with it the whole tree is swept. Use --dry-run to see the list and
    how much space it would free first.
    """
    target = (path if path is not None else Path.cwd()).resolve()
    results = purge_dirs(
        target,
        frozenset({JUPYTER_CHECKPOINTS}),
        recursive=recursive,
        dry_run=dry_run,
        skip=resolve_skip(no_default_skips),
    )
    if not results:
        typer.echo(f"No {JUPYTER_CHECKPOINTS} folders under {target}")
        raise typer.Exit(0)

    results.sort(key=lambda r: str(r.path).lower())
    rows = [
        (
            truncate(str(r.path.relative_to(target)), 70),
            r.status.value,
            str(r.files),
            human_bytes(r.size),
            truncate(r.detail),
        )
        for r in results
    ]
    freed = sum(r.size for r in results if r.status is not Status.ERROR)
    verb = "would free" if dry_run else "freed"
    typer.echo(
        render_table(
            ("Folder", "Status", "Files", "Size", "Detail"),
            rows,
            banner="(dry-run: nothing was deleted)" if dry_run else None,
            summary=f"{summarize(r.status.value for r in results)} - {verb} {human_bytes(freed)}",
        )
    )
    failed = any(r.status in FAILURE_STATUSES for r in results)
    raise typer.Exit(1 if failed else 0)


@folder_app.command("size")
def size_cmd(
    path: PathArg = None,
    depth: Annotated[
        int, typer.Option("--depth", "-d", min=1, help="Levels of subfolder to list.")
    ] = 1,
    top: Annotated[int, typer.Option("--top", "-n", min=1, help="Number of rows to show.")] = 20,
    no_default_skips: NoDefaultSkipsOpt = False,
) -> None:
    """Show which subfolders of PATH hold the space, largest first.

    Folders deeper than --depth still count toward their ancestors' totals;
    they are just not listed on their own row.
    """
    target = (path if path is not None else Path.cwd()).resolve()
    rows_data, total_size, total_files = folder_sizes(
        target, depth=depth, skip=resolve_skip(no_default_skips)
    )
    shown = rows_data[:top]
    rows = [
        (
            truncate(str(r.path.relative_to(target))),
            human_bytes(r.size),
            str(r.files),
            f"{100 * r.size / total_size:.0f}%" if total_size else "-",
        )
        for r in shown
    ]
    hidden = len(rows_data) - len(shown)
    summary = f"{human_bytes(total_size)} in {total_files} file(s) under {target}"
    if hidden:
        summary += f" ({hidden} more folder(s) not shown)"
    typer.echo(render_table(("Folder", "Size", "Files", "Share"), rows, summary=summary))
