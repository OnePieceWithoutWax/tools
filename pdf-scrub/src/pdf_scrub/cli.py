"""Command-line entry point for pdf-scrub."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from pdf_scrub.scrub import scrub

app = typer.Typer(help="Scrub PDFs of mailto links and watermarks.", add_completion=False)


@app.command()
def main_command(
    input_pdf: Annotated[Path, typer.Argument(help="Input PDF file.")],
    output_pdf: Annotated[
        Path | None, typer.Argument(help="Output PDF file (default: overwrite input).")
    ] = None,
    no_mailto: Annotated[
        bool, typer.Option("--no-mailto", help="Skip mailto link removal.")
    ] = False,
    no_watermarks: Annotated[
        bool, typer.Option("--no-watermarks", help="Skip watermark removal.")
    ] = False,
) -> None:
    """Scrub a PDF of mailto links and watermarks."""
    if not input_pdf.exists():
        typer.echo(f"Error: {input_pdf} not found.", err=True)
        raise typer.Exit(1)

    stats = scrub(
        input_pdf,
        output_pdf,
        mailto=not no_mailto,
        watermarks=not no_watermarks,
    )

    out_label = output_pdf or input_pdf
    typer.echo(f"Saved -> {out_label}")
    for key, val in stats.items():
        typer.echo(f"  {key}: {val} removed")


def main() -> None:
    """Console-script entry point."""
    app()
