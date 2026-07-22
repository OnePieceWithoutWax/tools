"""Option and argument types shared by both sub-apps."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from fdt.report import parse_size
from fdt.walk import DEFAULT_SKIP

SKIP_HELP = (
    "Also process .git, .venv, node_modules, __pycache__ and friends, which are skipped by default."
)

PathArg = Annotated[
    Path | None,
    typer.Argument(
        exists=True,
        file_okay=False,
        help="Folder to work on. Defaults to the current directory.",
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
NoDefaultSkipsOpt = Annotated[bool, typer.Option("--no-default-skips", help=SKIP_HELP)]


def resolve_skip(no_default_skips: bool) -> frozenset[str]:
    """The set of directory names to skip, given the ``--no-default-skips`` flag."""
    return frozenset() if no_default_skips else DEFAULT_SKIP


def size_option(text: str | None) -> int:
    """Parse a ``--min-size`` value, turning a bad one into a clean CLI error."""
    if text is None:
        return 0
    try:
        return parse_size(text)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from None
