"""Recorded no-legs run fixture for the byte-identity gate
(`research-frozen-partial-take-ladder-v1` task 0.1).

A local projection and market frame, no live Engine and no market data
load. One run covers both sides and every closing path the gate must
protect: initial stop, final take, signal, runtime exit, managed stop,
and a position left open at range end. The market is continuous: each
bar opens at the previous close, so no bar opens beyond an active stop
or final take level.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from research_service.accounting import AccountingPolicy
from research_service.application.backtests import SingleInstanceBacktestRequest
from research_service.domain.contracts import (
    Candle,
    ExecutableEntryOpportunityDTO,
    ExitAttributionDTO,
    ExplicitRange,
    HistoricalExecutionProjectionDTO,
    HistoricalManagedProjectionDTO,
    InitialProtectionLegDTO,
    MarketFrame,
    MarketRange,
    SignalExitCandidateDTO,
    SignalExitEventDTO,
    SignalExitProjectionDTO,
)
from research_service.domain.execution import ExecutionPolicy
from test_single_instance_backtest import strategy_identity

STEP_MS = 300_000

# Closes per bar. Opens are the previous close; wicks add 0.2 each way.
GATE_CLOSES: tuple[str, ...] = (
    "100",  # 0  long entry (stop 98, take 105)
    "99",  # 1
    "97.5",  # 2  long initial stop at 98
    "97",  # 3  short entry (stop 98.94, take 94.09)
    "96",  # 4
    "94",  # 5  short final take at 94.09
    "95",  # 6  long entry, signal profile
    "95.5",  # 7
    "96",  # 8  long signal exit at close
    "95",  # 9  short entry, runtime exit armed at bar 11
    "95.2",  # 10
    "95.1",  # 11 runtime condition
    "95.3",  # 12 short runtime exit at close
    "96",  # 13 long entry, proven at bar 15
    "96.5",  # 14
    "97",  # 15 to proven: managed stop 96.5 effective bar 16
    "97.2",  # 16
    "96.4",  # 17 long managed stop at 96.5
    "96",  # 18
    "96",  # 19
    "96",  # 20
    "96",  # 21
    "96",  # 22 short entry, left open
    "95.8",  # 23
    "95.9",  # 24
    "95.7",  # 25
)

GATE_BAR_COUNT = len(GATE_CLOSES)
_WICK = Decimal("0.2")


def gate_market_frame() -> MarketFrame:
    candles = []
    previous = Decimal(GATE_CLOSES[0])
    for index, raw_close in enumerate(GATE_CLOSES):
        close = Decimal(raw_close)
        open_ = previous
        candles.append(
            Candle(
                open_time_ms=index * STEP_MS,
                open=open_,
                high=max(open_, close) + _WICK,
                low=min(open_, close) - _WICK,
                close=close,
                volume=Decimal("1"),
            )
        )
        previous = close
    return MarketFrame(
        market=gate_market_range(),
        candles=tuple(candles),
        market_data_hash="market-hash",
    )


def gate_market_range() -> MarketRange:
    return MarketRange(
        ticker="BTCUSDT.P",
        timeframe="5m",
        from_ms=0,
        to_ms=GATE_BAR_COUNT * STEP_MS,
    )


def _leg(ratio: float, rule_id: str, exit_kind: str) -> InitialProtectionLegDTO:
    return InitialProtectionLegDTO(
        ratio=ratio,
        attribution=ExitAttributionDTO(
            rule_id=rule_id, component_id=f"{rule_id}_component", exit_kind=exit_kind
        ),
    )


def _opportunity(
    bar_index: int,
    side: str,
    profile: str,
    *,
    stop: float,
    take: float | None,
) -> ExecutableEntryOpportunityDTO:
    return ExecutableEntryOpportunityDTO(
        bar_index=bar_index,
        side=side,
        locked_exit_profile=profile,
        initial_stop=_leg(stop, "sl", "stop_loss"),
        initial_take=_leg(take, "tp", "take_profit") if take is not None else None,
    )


def gate_opportunities() -> tuple[ExecutableEntryOpportunityDTO, ...]:
    return (
        _opportunity(0, "long", "aligned", stop=0.02, take=0.05),
        _opportunity(3, "short", "aligned", stop=0.02, take=0.03),
        _opportunity(6, "long", "neutral", stop=0.10, take=0.10),
        _opportunity(9, "short", "countertrend", stop=0.10, take=0.10),
        _opportunity(13, "long", "aligned", stop=0.10, take=None),
        _opportunity(22, "short", "aligned", stop=0.10, take=0.10),
    )


def _signal_events() -> SignalExitProjectionDTO:
    signal = SignalExitEventDTO(
        bar_index=8,
        candidates=(
            SignalExitCandidateDTO(
                attribution=ExitAttributionDTO(
                    rule_id="sig", component_id="sig_component", exit_kind="signal"
                )
            ),
        ),
    )
    return SignalExitProjectionDTO(
        long={"aligned": (), "countertrend": (), "neutral": (signal,)},
        short={"aligned": (), "countertrend": (), "neutral": ()},
    )


def _flag(true_at: set[int]) -> dict[str, list[bool]]:
    values = [index in true_at for index in range(GATE_BAR_COUNT)]
    return {"long": values, "short": values}


def gate_managed_projection() -> HistoricalManagedProjectionDTO:
    rules: list[dict[str, Any]] = [
        {
            "kind": "phase_transition",
            "rule_id": "to_proven",
            "target_phase": "proven",
            "condition_id": "proven",
            "distance_id": None,
            "trade_metric": None,
        },
        {
            "kind": "stop_action",
            "rule_id": "be",
            "activation_phase": "proven",
            "distance_id": "be",
        },
        {
            "kind": "runtime_exit",
            "rule_id": "rt",
            "activation_phase": "initial_risk",
            "condition_id": "runtime",
            "confirm_bars": 1,
            "exit_class": "runtime_close",
        },
    ]
    return HistoricalManagedProjectionDTO.model_validate(
        {
            "conditions": {"proven": _flag({15}), "runtime": _flag({11})},
            "distances": {"be": [0.5] * GATE_BAR_COUNT},
            "rules": rules,
        }
    )


def gate_projection(
    opportunities: tuple[ExecutableEntryOpportunityDTO, ...] | None = None,
) -> HistoricalExecutionProjectionDTO:
    return HistoricalExecutionProjectionDTO(
        contract_version="strategy_evaluation_execution.v2",
        strategy_id="ema_pullback",
        config_hash="config-hash",
        market=gate_market_range(),
        market_data_hash="market-hash",
        bar_count=GATE_BAR_COUNT,
        entry_opportunities=opportunities if opportunities is not None else gate_opportunities(),
        signal_exit_events=_signal_events(),
        managed=gate_managed_projection(),
        warnings=(),
    )


def gate_request() -> SingleInstanceBacktestRequest:
    return SingleInstanceBacktestRequest(
        strategy=strategy_identity(),
        range=ExplicitRange(from_ms=0, to_ms=GATE_BAR_COUNT * STEP_MS),
        execution=ExecutionPolicy(),
        accounting=AccountingPolicy(
            initial_equity=Decimal("1000"),
            entry_fee_rate=Decimal("0.001"),
            exit_fee_rate=Decimal("0.001"),
        ),
        managed_policy_enabled=True,
    )
