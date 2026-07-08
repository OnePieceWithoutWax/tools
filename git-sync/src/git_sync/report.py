"""Summary table output."""

from __future__ import annotations

from collections import Counter

from git_sync.repo import RepoResult

_HEADERS = ("Repo", "Branch", "Status", "Behind", "Ahead", "Detail")
_MAX_DETAIL = 60


def render_table(results: list[RepoResult], dry_run: bool = False) -> str:
    """Render results as a plain-text summary table.

    Args:
        results: Per-repo sync results.
        dry_run: Adds a banner noting no changes were made.

    Returns:
        The table as a multi-line string.
    """
    rows = [
        (
            r.name,
            r.branch,
            r.status.value,
            str(r.behind),
            str(r.ahead),
            r.detail[:_MAX_DETAIL],
        )
        for r in results
    ]
    widths = [
        max(len(_HEADERS[i]), *(len(row[i]) for row in rows)) if rows else len(_HEADERS[i])
        for i in range(len(_HEADERS))
    ]

    def line(cells: tuple[str, ...]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells)).rstrip()

    lines = []
    if dry_run:
        lines.append("(dry-run: no changes made)")
    lines.append(line(_HEADERS))
    lines.append(line(tuple("-" * w for w in widths)))
    lines.extend(line(row) for row in rows)

    counts = Counter(r.status.value for r in results)
    summary = ", ".join(f"{n} {status}" for status, n in sorted(counts.items()))
    lines.append(f"\n{len(results)} repo(s): {summary}")
    return "\n".join(lines)
