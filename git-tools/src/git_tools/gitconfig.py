"""Read one git config key across many repos, optionally checking it."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fnmatch import fnmatch
from pathlib import Path

from git_tools.gitcmd import run_git

UNSET = "(unset)"


class ConfigStatus(StrEnum):
    """Outcome of reading a config key in one repository."""

    OK = "OK"
    MISMATCH = "MISMATCH"
    UNSET = "UNSET"


CONFIG_FAILURE_STATUSES = frozenset({ConfigStatus.MISMATCH, ConfigStatus.UNSET})


@dataclass
class ConfigResult:
    """The value of one config key in one repository."""

    path: Path
    name: str
    key: str
    value: str
    status: ConfigStatus
    detail: str = ""


def read_config(path: Path, key: str, *, expect: str | None = None) -> ConfigResult:
    """Read ``key`` in one repo, comparing it to ``expect`` when given.

    The effective value is read (``git config --get``), so a value inherited
    from global config or an ``includeIf`` block is what you see — which is the
    point when auditing which identity a repo commits under.

    Args:
        path: Repository working directory.
        key: Config key, e.g. ``user.email``.
        expect: Optional glob (``fnmatch``, case-insensitive). A value not
            matching it is reported as MISMATCH.

    Returns:
        A ConfigResult holding the value and how it compared.
    """
    proc = run_git(path, "config", "--get", key)
    value = proc.stdout.strip()

    if proc.returncode != 0 or not value:
        return ConfigResult(
            path=path,
            name=path.name,
            key=key,
            value=UNSET,
            status=ConfigStatus.UNSET,
            detail=f"{key} is not set",
        )

    if expect is not None and not fnmatch(value.lower(), expect.lower()):
        return ConfigResult(
            path=path,
            name=path.name,
            key=key,
            value=value,
            status=ConfigStatus.MISMATCH,
            detail=f"does not match {expect}",
        )

    return ConfigResult(path=path, name=path.name, key=key, value=value, status=ConfigStatus.OK)
