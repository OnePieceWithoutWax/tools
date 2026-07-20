"""Plain-text table output shared by every command."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence

MAX_DETAIL = 60


def truncate(text: str, limit: int = MAX_DETAIL) -> str:
    """Shorten ``text`` to ``limit`` characters, marking that it was cut.

    Stays ASCII: these tables are read in the Windows console, where a stray
    multi-byte character can render as a replacement glyph.
    """
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


def summarize(statuses: Iterable[str], noun: str = "repo") -> str:
    """A ``"3 repo(s): 2 PULLED, 1 DIRTY"`` style tally line."""
    counts = Counter(statuses)
    total = sum(counts.values())
    tally = ", ".join(f"{n} {status}" for status, n in sorted(counts.items()))
    return f"{total} {noun}(s): {tally}" if tally else f"0 {noun}(s)"


def render_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    banner: str | None = None,
    summary: str | None = None,
) -> str:
    """Render rows as a column-aligned plain-text table.

    Args:
        headers: Column headings.
        rows: Row cells, each the same length as ``headers``.
        banner: Optional line printed above the table (e.g. a dry-run notice).
        summary: Optional tally line printed below the table.

    Returns:
        The table as a multi-line string.
    """
    widths = [
        max(len(headers[i]), *(len(row[i]) for row in rows)) if rows else len(headers[i])
        for i in range(len(headers))
    ]

    def line(cells: Sequence[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells)).rstrip()

    lines: list[str] = []
    if banner:
        lines.append(banner)
    lines.append(line(headers))
    lines.append(line(["-" * w for w in widths]))
    lines.extend(line(row) for row in rows)
    if summary:
        lines.append(f"\n{summary}")
    return "\n".join(lines)
