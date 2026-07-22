"""Outcome vocabulary shared by the commands that delete things."""

from __future__ import annotations

from enum import StrEnum


class Status(StrEnum):
    """What happened to one directory."""

    DELETED = "DELETED"
    WOULD_DELETE = "WOULD_DELETE"
    ERROR = "ERROR"


FAILURE_STATUSES = frozenset({Status.ERROR})
