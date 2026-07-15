"""Filesystem-safe ``run_id`` validation for BFF path joins."""

from __future__ import annotations

import re

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_\-\.]+$")


class InvalidRunIdError(ValueError):
    """``run_id`` contains disallowed characters or path separators."""

    def __init__(self, run_id: str) -> None:
        super().__init__(f"Invalid run_id: {run_id!r}")
        self.run_id = run_id


def validate_run_id(run_id: str) -> str:
    """Allow alnum, underscore, dash, dot; reject path separators."""

    if run_id != run_id.strip():
        raise InvalidRunIdError(run_id)
    if not run_id:
        raise InvalidRunIdError(run_id)
    if "/" in run_id or "\\" in run_id:
        raise InvalidRunIdError(run_id)
    if ".." in run_id:
        raise InvalidRunIdError(run_id)
    if not _RUN_ID_RE.fullmatch(run_id):
        raise InvalidRunIdError(run_id)
    return run_id
