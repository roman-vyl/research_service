"""Opt-in pipeline step counters and timings (stderr tables). Enable with EMA_PIPELINE_DEBUG=1."""

from __future__ import annotations

import os
import sys
import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Any, Iterator

_enabled: bool | None = None
_root: str | None = None
_stats: dict[str, dict[str, float | int | Any]] = defaultdict(
    lambda: {"count": 0, "total_ms": 0.0, "max_ms": 0.0}
)


def pipeline_debug_enabled() -> bool:
    global _enabled
    if _enabled is None:
        _enabled = os.environ.get("EMA_PIPELINE_DEBUG", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
    return _enabled


def _record(step: str, elapsed_ms: float, **meta: Any) -> None:
    row = _stats[step]
    row["count"] = int(row["count"]) + 1
    row["total_ms"] = float(row["total_ms"]) + elapsed_ms
    if elapsed_ms > float(row["max_ms"]):
        row["max_ms"] = elapsed_ms
    if meta:
        row["last_meta"] = meta


@contextmanager
def dbg_root(name: str) -> Iterator[None]:
    global _root, _stats
    if not pipeline_debug_enabled():
        yield
        return
    prev_root = _root
    prev_stats = _stats
    _root = name
    _stats = defaultdict(lambda: {"count": 0, "total_ms": 0.0, "max_ms": 0.0})
    try:
        yield
    finally:
        dbg_flush(root=name)
        _root = prev_root
        _stats = prev_stats


@contextmanager
def dbg_span(step: str) -> Iterator[None]:
    if not pipeline_debug_enabled():
        yield
        return
    t0 = time.perf_counter()
    try:
        yield
    finally:
        _record(step, (time.perf_counter() - t0) * 1000.0)


def dbg_mark(step: str, **meta: Any) -> None:
    if not pipeline_debug_enabled():
        return
    _record(step, 0.0, **meta)


def dbg_flush(*, root: str | None = None) -> None:
    if not pipeline_debug_enabled():
        return
    label = root or _root or "pipeline"
    col_step = 44
    lines = [
        "",
        f"=== PIPELINE_DEBUG [{label}] ===",
        f"{'step':<{col_step}} {'count':>6} {'total_ms':>10} {'max_ms':>10}",
        "-" * (col_step + 30),
    ]
    for step in sorted(_stats.keys()):
        row = _stats[step]
        count = int(row["count"])
        prefix = "REPEAT " if count > 1 else ""
        lines.append(
            f"{prefix}{step:<{col_step}} {count:>6} "
            f"{float(row['total_ms']):>10.1f} {float(row['max_ms']):>10.1f}"
        )
    lines.append("=== end ===\n")
    print("\n".join(lines), file=sys.stderr, flush=True)
