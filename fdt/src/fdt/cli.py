"""Command-line entry point.

Naming convention
-----------------
Commands are grouped by what they act on: ``fdt folder <verb>`` for operations
on directories, ``fdt file <verb>`` for operations on files. Every command
takes an optional folder argument that defaults to the current directory, and
anything that changes the disk takes ``--dry-run``.
"""

from __future__ import annotations

from importlib.metadata import version as _pkg_version
from typing import Annotated

import typer

from fdt.cli_file import file_app
from fdt.cli_folder import folder_app

app = typer.Typer(add_completion=False, no_args_is_help=True)
app.add_typer(folder_app, name="folder")
app.add_typer(file_app, name="file")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(_pkg_version("fdt"))
        raise typer.Exit(0)


@app.callback()
def callback(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the fdt version and exit.",
        ),
    ] = False,
) -> None:
    """File and directory housekeeping."""


def main() -> None:
    """Console-script entry point."""
    app()
