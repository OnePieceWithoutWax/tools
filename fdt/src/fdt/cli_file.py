"""The ``fdt file`` sub-app: commands that act on files."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from fdt.dupes import find_dupes
from fdt.options import NoDefaultSkipsOpt, PathArg, resolve_skip, size_option
from fdt.report import human_bytes, render_table, truncate
from fdt.sizes import largest_files

file_app = typer.Typer(add_completion=False, no_args_is_help=True, help="File commands.")

MinSizeOpt = Annotated[
    str | None,
    typer.Option("--min-size", "-m", help="Ignore files below this size, e.g. 500, 10MB, 1.5G."),
]


@file_app.command("find-large")
def find_large_cmd(
    path: PathArg = None,
    top: Annotated[int, typer.Option("--top", "-n", min=1, help="Number of files to show.")] = 20,
    min_size: MinSizeOpt = None,
    no_default_skips: NoDefaultSkipsOpt = False,
) -> None:
    """List the largest files under PATH (default: the current directory)."""
    target = (path if path is not None else Path.cwd()).resolve()
    found = largest_files(
        target,
        top=top,
        min_size=size_option(min_size),
        skip=resolve_skip(no_default_skips),
    )
    if not found:
        typer.echo(f"No matching files under {target}")
        raise typer.Exit(0)

    rows = [(truncate(str(f.path.relative_to(target)), 70), human_bytes(f.size)) for f in found]
    typer.echo(
        render_table(
            ("File", "Size"),
            rows,
            summary=f"{len(found)} file(s), {human_bytes(sum(f.size for f in found))} total",
        )
    )


@file_app.command("find-dupes")
def find_dupes_cmd(
    path: PathArg = None,
    min_size: MinSizeOpt = None,
    top: Annotated[
        int, typer.Option("--top", "-n", min=1, help="Number of duplicate groups to show.")
    ] = 20,
    no_default_skips: NoDefaultSkipsOpt = False,
) -> None:
    """Find byte-identical files under PATH, worst offenders first.

    Reports only -- nothing is deleted. Files are compared by size, then by
    their first 64 KiB, then in full, so a reported group is a genuine content
    match and not a hash guess.
    """
    target = (path if path is not None else Path.cwd()).resolve()
    groups = find_dupes(
        target,
        min_size=max(size_option(min_size), 1),
        skip=resolve_skip(no_default_skips),
    )
    if not groups:
        typer.echo(f"No duplicate files under {target}")
        raise typer.Exit(0)

    shown = groups[:top]
    rows: list[tuple[str, str, str, str]] = []
    for index, group in enumerate(shown, start=1):
        for position, dupe in enumerate(group.paths):
            rows.append(
                (
                    str(index) if position == 0 else "",
                    human_bytes(group.size) if position == 0 else "",
                    "keep" if position == 0 else "dupe",
                    truncate(str(dupe.relative_to(target)), 70),
                )
            )

    wasted = sum(g.wasted for g in groups)
    summary = (
        f"{len(groups)} group(s), {sum(len(g.paths) for g in groups)} file(s), "
        f"{human_bytes(wasted)} recoverable"
    )
    if len(shown) < len(groups):
        summary += f" ({len(groups) - len(shown)} group(s) not shown)"
    typer.echo(render_table(("#", "Size", "Role", "File"), rows, summary=summary))
