"""Low-level git invocation shared by every command."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command in ``repo``.

    Runs plain git with the inherited environment — no ``-c`` credential or
    auth overrides, so per-repo config (includeIf / multi-account HTTPS
    setups) applies as configured. Terminal credential prompts are disabled
    so an unauthenticated repo fails instead of hanging a worker thread.

    Args:
        repo: Repository working directory.
        *args: Git subcommand and arguments.

    Returns:
        The completed process with captured text output; never raises on
        non-zero exit.
    """
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )


def first_line(text: str) -> str:
    """The first non-blank line of ``text``, or an empty string."""
    return text.strip().splitlines()[0] if text.strip() else ""


def current_branch(repo: Path) -> str:
    """Current branch short name, ``HEAD`` when detached, ``?`` on failure."""
    proc = run_git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    return proc.stdout.strip() if proc.returncode == 0 else "?"
