"""Verbatim old-BBB trade-lifecycle mechanics -- I5 Lane B independent
reference (`compact-strategy-evaluation-boundary-v1`, Master Plan I5.C).

Provenance
----------
Repository: `roman-vyl/_bbb_new_gen`
Commit:     `cddc83663911f646c9bcf2ecfb37b3bed6f4b1d4`
Path:       `research/strategies/ema_pullback/execution/exit_attribution.py`

`_finite`, `_levels_from_ratios`, `_stop_hit_long`, `_stop_hit_short`,
`fill_price_for_distance_exit` below are copied character-for-character
from that file at that commit (the same provenance already established
for `strategy_engine`'s I2 proof, `tests/_old_bbb_exit_attribution_
reference.py`) -- no logic altered. These are old BBB's own OHLC-gap
stop/take hit-detection and fill-price mechanics (mirroring vectorbt's
`get_stop_price_nb`), independent of anything in `execution/
projection_loop.py`/`execution/projection_entry.py`/`execution/
projection_static_exits.py` or Research's legacy execution path -- this
module imports nothing from either.

`_pick_distance_instance`-equivalent selection and locked-profile
signal-winner selection are NOT reimplemented here: this Lane B
reference deliberately reuses the real, already-I2-proven-correct
`ExecutableEntryOpportunityDTO.initial_stop`/`.initial_take` ratios and
`SignalExitEventDTO.candidates[0]` from the real v2 projection as INPUT
DATA (exactly as I2's own reference did against Engine's real
`rule_evidence`) -- not as the algorithm under test. What Lane B
independently verifies is the EXECUTION lifecycle built on top of that
data: locked-profile capture and persistence, protection-level
resolution, OHLC exit-hit detection/fill price, same-bar-arbitration
priority (stop < take < signal, old BBB's own documented order in
`classify_exit_attribution`), and accounting -- reimplemented here from
scratch, never by calling `execution/projection_*.py`.
"""

from __future__ import annotations

import math
from typing import Literal


def _finite(x: object) -> bool:
    if x is None:
        return False
    try:
        v = float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return math.isfinite(v)


def _levels_from_ratios(
    direction: str,
    stop_anchor: float,
    sl_r: float | None,
    tp_r: float | None,
) -> tuple[float | None, float | None]:
    """Absolute SL/TP levels from vectorbt default ``stop_entry_price`` = close (long/short formulas)."""

    if direction == "long":
        sl_level = stop_anchor * (1.0 - sl_r) if sl_r is not None else None
        tp_level = stop_anchor * (1.0 + tp_r) if tp_r is not None else None
        return sl_level, tp_level
    sl_level = stop_anchor * (1.0 + sl_r) if sl_r is not None else None
    tp_level = stop_anchor * (1.0 - tp_r) if tp_r is not None else None
    return sl_level, tp_level


def _stop_hit_long(
    o: float,
    h: float,
    l: float,  # noqa: E741 -- verbatim old-BBB parameter name
    level: float,
    *,
    is_loss: bool,
) -> bool:
    """Mirror vectorbt ``get_stop_price_nb`` hit semantics (long: SL below, TP above)."""

    if is_loss:
        stop_price = level
        if o <= stop_price:
            return True
        return l <= stop_price <= h
    stop_price = level
    if stop_price <= o:
        return True
    return l <= stop_price <= h


def _stop_hit_short(
    o: float,
    h: float,
    l: float,  # noqa: E741 -- verbatim old-BBB parameter name
    level: float,
    *,
    is_loss: bool,
) -> bool:
    """Short: SL above anchor; TP below."""

    if is_loss:
        stop_price = level
        if stop_price <= o:
            return True
        return l <= stop_price <= h
    stop_price = level
    if o <= stop_price:
        return True
    return l <= stop_price <= h


def fill_price_for_distance_exit(
    direction: Literal["long", "short"],
    *,
    open_: float,
    high: float,
    low: float,
    level: float,
    is_loss: bool,
) -> float:
    """Fill price when a distance stop/TP level is hit (mirrors ``get_stop_price_nb``)."""

    if direction == "long":
        if is_loss:
            if open_ <= level:
                return open_
            if low <= level <= high:
                return level
        else:
            if level <= open_:
                return open_
            if low <= level <= high:
                return level
    else:
        if is_loss:
            if level <= open_:
                return open_
            if low <= level <= high:
                return level
        else:
            if open_ <= level:
                return open_
            if low <= level <= high:
                return level
    return level
