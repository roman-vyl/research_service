"""Shared harness for partial take ladder tests
(`research-frozen-partial-take-ladder-v1` groups 4-6).

Master plan §7 example: Q0 = 100, anchor/entry 100 on bar 0, stop 5%
(95 long / 105 short), legs 1% and 3% of 25% each (101/103 long,
99/97 short), final take 8% (108 long / 92 short).
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from research_service.domain.contracts import (
    Candle,
    ExecutableEntryOpportunityDTO,
    ExitAttributionDTO,
    HistoricalExecutionProjectionDTO,
    HistoricalExecutionProjectionIndex,
    HistoricalManagedProjectionDTO,
    InitialProtectionLegDTO,
    MarketFrame,
    MarketRange,
    PartialTakeLegDTO,
    SignalExitCandidateDTO,
    SignalExitEventDTO,
    SignalExitProjectionDTO,
)
from research_service.domain.execution import ExecutionLoopResult, ExecutionPolicy
from research_service.execution.projection_loop import run_projection_execution_loop

STEP_MS = 300_000
Q0 = Decimal("100")
DEFAULT_LEGS: tuple[tuple[str, float, float], ...] = (("tp1", 0.01, 0.25), ("tp2", 0.03, 0.25))
FLAT: tuple[str, str, str, str] = ("100", "100", "100", "100")

Bar = tuple[str, str, str, str]


def _attribution(rule_id: str, kind: str, component: str = "c") -> ExitAttributionDTO:
    return ExitAttributionDTO(rule_id=rule_id, component_id=component, exit_kind=kind)


def opportunity(
    side: str,
    *,
    legs: Sequence[tuple[str, float, float]] = DEFAULT_LEGS,
    take: float | None = 0.08,
    stop: float | None = 0.05,
) -> ExecutableEntryOpportunityDTO:
    return ExecutableEntryOpportunityDTO(
        bar_index=0,
        side=side,
        locked_exit_profile="aligned",
        initial_stop=None
        if stop is None
        else InitialProtectionLegDTO(ratio=stop, attribution=_attribution("sl", "stop_loss")),
        initial_take=None
        if take is None
        else InitialProtectionLegDTO(ratio=take, attribution=_attribution("tp", "take_profit")),
        partial_takes=tuple(
            PartialTakeLegDTO(
                take_id=take_id,
                ratio=ratio,
                fraction_of_initial=fraction,
                attribution=_attribution(take_id, "partial_take", "pct_partial_take"),
            )
            for take_id, ratio, fraction in legs
        ),
    )


def frame(bars: Sequence[Bar]) -> MarketFrame:
    return MarketFrame(
        market=MarketRange(
            ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=len(bars) * STEP_MS
        ),
        candles=tuple(
            Candle(
                open_time_ms=index * STEP_MS,
                open=open_,
                high=high,
                low=low,
                close=close,
                volume="1",
            )
            for index, (open_, high, low, close) in enumerate(bars)
        ),
        market_data_hash="market-hash",
    )


def projection(
    side: str,
    bar_count: int,
    *,
    opportunity_dto: ExecutableEntryOpportunityDTO,
    signal_bars: Sequence[int] = (),
    managed: HistoricalManagedProjectionDTO | None = None,
) -> HistoricalExecutionProjectionDTO:
    events = tuple(
        SignalExitEventDTO(
            bar_index=bar,
            candidates=(SignalExitCandidateDTO(attribution=_attribution("sig", "signal")),),
        )
        for bar in signal_bars
    )
    empty: dict[str, tuple[Any, ...]] = {"aligned": (), "countertrend": (), "neutral": ()}
    with_events = {**empty, "aligned": events}
    return HistoricalExecutionProjectionDTO(
        contract_version="strategy_evaluation_execution.v2",
        strategy_id="ema_pullback",
        config_hash="config-hash",
        market=frame([FLAT] * bar_count).market,
        market_data_hash="market-hash",
        bar_count=bar_count,
        entry_opportunities=(opportunity_dto,),
        signal_exit_events=SignalExitProjectionDTO(
            long=with_events if side == "long" else empty,
            short=with_events if side == "short" else empty,
        ),
        managed=managed,
        warnings=(),
    )


def managed_projection(
    rules: list[dict[str, Any]],
    *,
    bar_count: int,
    conditions: dict[str, set[int]] | None = None,
    distances: dict[str, float] | None = None,
) -> HistoricalManagedProjectionDTO:
    return HistoricalManagedProjectionDTO.model_validate(
        {
            "conditions": {
                key: {
                    "long": [i in bars for i in range(bar_count)],
                    "short": [i in bars for i in range(bar_count)],
                }
                for key, bars in (conditions or {}).items()
            },
            "distances": {key: [value] * bar_count for key, value in (distances or {}).items()},
            "rules": rules,
        }
    )


def run(
    side: str,
    bars: Sequence[Bar],
    *,
    entry_bar: Bar = FLAT,
    legs: Sequence[tuple[str, float, float]] = DEFAULT_LEGS,
    take: float | None = 0.08,
    stop: float | None = 0.05,
    signal_bars: Sequence[int] = (),
    managed: HistoricalManagedProjectionDTO | None = None,
) -> ExecutionLoopResult:
    all_bars = [entry_bar, *bars]
    dto = projection(
        side,
        len(all_bars),
        opportunity_dto=opportunity(side, legs=legs, take=take, stop=stop),
        signal_bars=signal_bars,
        managed=managed,
    )
    return run_projection_execution_loop(
        "instance-1",
        HistoricalExecutionProjectionIndex.build(dto),
        frame(all_bars),
        ExecutionPolicy(),
        entry_quantity_provider=lambda _decision, _price: Q0,
        managed_replay_provider=(lambda _position: None) if managed is not None else None,
    )


def fills(result: ExecutionLoopResult) -> list[tuple[int, str, Decimal, Decimal]]:
    """`(bar, kind, price, quantity)` for every reduction and the closing
    fill of the single position, in execution order."""

    (execution,) = result.positions
    observed = [
        (item.bar_index, item.take_id, item.fill_price, item.quantity)
        for item in execution.reductions
    ]
    if execution.exit_fill is not None:
        observed.append(
            (
                execution.exit_fill.bar_index,
                execution.exit_fill.candidate_type,
                execution.exit_fill.fill_price,
                execution.remaining_quantity,
            )
        )
    return observed


def D(value: str) -> Decimal:
    return Decimal(value)
