"""Plain-text table output shared by every command."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence

MAX_DETAIL = 60


def truncate(text: str, limit: int = MAX_DETAIL) -> str:
    """Shorten ``text`` to ``limit`` characters, marking that it was cut.

    Long paths are cut from the *left*: the tail (the file name) is what
    identifies a row, so the head is the part worth losing.
    """
    return text if len(text) <= limit else f"...{text[-(limit - 3) :]}"


def summarize(statuses: Iterable[str], noun: str = "folder") -> str:
    """A ``"3 folder(s): 2 DELETED, 1 ERROR"`` style tally line."""
    counts = Counter(statuses)
    total = sum(counts.values())
    tally = ", ".join(f"{n} {status}" for status, n in sorted(counts.items()))
    return f"{total} {noun}(s): {tally}" if tally else f"0 {noun}(s)"


def human_bytes(size: int) -> str:
    """Format a byte count as a short human-readable string, e.g. ``1.4 GB``.

    Stays ASCII: these tables are read in the Windows console, where a stray
    multi-byte character can render as a replacement glyph.
    """
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")  # pragma: no cover


_UNITS = {"B": 1, "K": 1024, "KB": 1024, "M": 1024**2, "MB": 1024**2, "G": 1024**3, "GB": 1024**3}


def parse_size(text: str) -> int:
    """Parse a size like ``500``, ``10MB`` or ``1.5G`` into bytes.

    Raises:
        ValueError: If the text is not a number with an optional unit suffix.
    """
    cleaned = text.strip().upper().replace(" ", "")
    for suffix in sorted(_UNITS, key=len, reverse=True):
        if cleaned.endswith(suffix):
            number, unit = cleaned[: -len(suffix)], _UNITS[suffix]
            break
    else:
        number, unit = cleaned, 1
    try:
        return int(float(number) * unit)
    except ValueError:
        raise ValueError(f"not a size: {text!r} (try 500, 10MB, 1.5G)") from None


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
