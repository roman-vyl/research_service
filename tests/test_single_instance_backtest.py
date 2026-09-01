from __future__ import annotations

from decimal import Decimal
from collections.abc import Iterator
from typing import Any

import pytest

from research_service.accounting import AccountingPolicy
from research_service.application.backtests import (
    MaterializeBacktestProjectionOutcome,
    RunSingleInstanceBacktest,
    SingleInstanceBacktestRequest,
)
from research_service.domain.contracts import (
    Candle,
    ContinuityAudit,
    ExecutableEntryOpportunityDTO,
    ExitAttributionDTO,
    ExplicitRange,
    HistoricalExecutionProjectionDTO,
    InitialProtectionLegDTO,
    ManagedBarDecision,
    ManagedReplayRequest,
    ManagedReplayResult,
    MarketFrame,
    MarketRange,
    SignalExitProjectionDTO,
    StrategyEvaluationBatchRequest,
    StrategyEvaluationBatchVariantOutcome,
    StrategyEvaluationRequest,
    StrategyEvaluationResult,
    StreamBounds,
)
from research_service.domain.errors import InvalidRequest, UpstreamServiceError
from research_service.domain.execution import ExecutionPolicy
from research_service.domain.strategy_instance import (
    StrategyInstanceIdentity,
    derive_strategy_instance_id,
)

_RAW_SPEC = {"anchor": {"period": 200}}

# The identity subset every fixture in this module agrees on. instance_id is
# derived from these four fields, never a literal — so every place that used
# to hardcode "instance-1" now derives it here once.
INSTANCE_ID = derive_strategy_instance_id(
    strategy_id="ema_pullback",
    ticker="BTCUSDT.P",
    base_timeframe="5m",
    raw_spec=_RAW_SPEC,
)

_EMPTY_PROFILE_EVENTS: dict[str, tuple[Any, ...]] = {
    "aligned": (),
    "countertrend": (),
    "neutral": (),
}


def market_frame() -> MarketFrame:
    market = MarketRange(
        ticker="BTCUSDT.P",
        timeframe="5m",
        from_ms=0,
        to_ms=900_000,
    )
    return MarketFrame(
        market=market,
        candles=(
            Candle(open_time_ms=0, open="99", high="102", low="98", close="100", volume="1"),
            Candle(open_time_ms=300_000, open="100", high="106", low="99", close="105", volume="1"),
            Candle(
                open_time_ms=600_000, open="105", high="106", low="103", close="104", volume="1"
            ),
        ),
        market_data_hash="market-hash",
    )


def strategy_identity() -> StrategyInstanceIdentity:
    """The canonical identity subset a `SingleInstanceBacktestRequest` embeds."""
    return StrategyInstanceIdentity(
        strategy_id="ema_pullback",
        ticker="BTCUSDT.P",
        base_timeframe="5m",
        raw_spec=_RAW_SPEC,
    )


def strategy_request() -> StrategyEvaluationRequest:
    """The Engine-wire request `run_backtest.py` constructs internally —
    still used to assert what `FakeStrategyEngine` actually received."""
    return StrategyEvaluationRequest(
        strategy_id="ema_pullback",
        instance_id=INSTANCE_ID,
        strategy_spec=_RAW_SPEC,
        market=market_frame().market,
    )


def strategy_projection(*, market: MarketRange | None = None) -> HistoricalExecutionProjectionDTO:
    """The `HistoricalExecutionProjection` (`.v2`) fixture -- a single long
    executable entry opportunity at bar 0, take-profit at 5%, stop-loss at
    10%, no signal exits (compact-strategy-evaluation-boundary-v1, I7)."""

    resolved_market = market or market_frame().market
    return HistoricalExecutionProjectionDTO(
        contract_version="strategy_evaluation_execution.v2",
        strategy_id="ema_pullback",
        config_hash="config-hash",
        market=resolved_market,
        market_data_hash="market-hash",
        bar_count=3,
        entry_opportunities=(
            ExecutableEntryOpportunityDTO(
                bar_index=0,
                side="long",
                locked_exit_profile="aligned",
                initial_stop=InitialProtectionLegDTO(
                    ratio=0.10,
                    attribution=ExitAttributionDTO(
                        rule_id="sl", component_id="c", exit_kind="stop_loss"
                    ),
                ),
                initial_take=InitialProtectionLegDTO(
                    ratio=0.05,
                    attribution=ExitAttributionDTO(
                        rule_id="tp", component_id="c", exit_kind="take_profit"
                    ),
                ),
            ),
        ),
        signal_exit_events=SignalExitProjectionDTO(
            long=_EMPTY_PROFILE_EVENTS, short=_EMPTY_PROFILE_EVENTS
        ),
        warnings=(),
    )


def strategy_result(*, market: MarketRange | None = None) -> StrategyEvaluationResult:
    """Legacy dense fixture -- batch's execution path only
    (`test_batch_experiments.py`); untouched by I7."""

    resolved_market = market or market_frame().market
    return StrategyEvaluationResult(
        contract_version="strategy_evaluation.v1",
        strategy_id="ema_pullback",
        instance_id=INSTANCE_ID,
        config_hash="config-hash",
        market=resolved_market,
        bar_count=3,
        market_data_hash="market-hash",
        time_ms=(0, 300_000, 600_000),
        entries={"long": (True, False, False), "short": (False, False, False)},
        exit_policy={
            "signal_exit": {"long": [False, False, False], "short": [False, False, False]},
            "stop_loss_ratio": {"long": ["0.10"] * 3, "short": ["0.10"] * 3},
            "take_profit_ratio": {"long": ["0.05"] * 3, "short": ["0.05"] * 3},
            "stop_ready": {"long": [True] * 3, "short": [True] * 3},
        },
        component_evidence={},
        raw={},
    )


class FakeStrategyEngine:
    """Shared fake across single-instance (`evaluate_range_projection`)
    and batch (`evaluate_range_batch`, `test_batch_experiments.py`) test
    suites -- since I8 both go through the same `.v2` projection-based
    path. `StrategyEvaluationResult` construction (`strategy_result()`)
    is retained only for the legacy dense-shape `evaluate_range_batch`
    fixture path. Accepts either fixture type and only wires the methods
    that type supports; the other side raises if called, catching an
    accidental cross-wiring in a test."""

    def __init__(
        self,
        result: HistoricalExecutionProjectionDTO | StrategyEvaluationResult,
        *,
        failing_variant_ids: frozenset[str] = frozenset(),
        shuffle_response: bool = False,
    ) -> None:
        self.projection = result if isinstance(result, HistoricalExecutionProjectionDTO) else None
        self.result = result if isinstance(result, StrategyEvaluationResult) else None
        self.range_requests: list[StrategyEvaluationRequest] = []
        self.batch_requests: list[StrategyEvaluationBatchRequest] = []
        self.managed_requests: list[ManagedReplayRequest] = []
        self.failing_variant_ids = failing_variant_ids
        self.shuffle_response = shuffle_response

    def evaluate_range_projection(
        self, request: StrategyEvaluationRequest
    ) -> HistoricalExecutionProjectionDTO:
        if self.projection is None:
            raise AssertionError("not used -- legacy dense fixture only")
        self.range_requests.append(request)
        return self.projection

    def evaluate_range_batch(
        self, request: StrategyEvaluationBatchRequest
    ) -> Iterator[StrategyEvaluationBatchVariantOutcome]:
        """I8: streamed, projection-based -- mirrors the real Engine's
        shared-once-acquisition + sequential per-variant `.v2` semantics.
        `instance_id` is never echoed on the projection (Research-owned,
        stamped downstream from the candidate's own identity subset) --
        only `strategy_id` varies per variant here, matching the real
        wire contract."""

        if self.projection is None:
            raise AssertionError("not used -- legacy dense fixture only")
        self.batch_requests.append(request)
        outcomes = []
        for variant in request.variants:
            if variant.variant_id in self.failing_variant_ids:
                outcomes.append(
                    StrategyEvaluationBatchVariantOutcome(
                        variant_id=variant.variant_id,
                        error={
                            "error": "invalid_request",
                            "message": f"boom:{variant.variant_id}",
                            "details": {},
                        },
                    )
                )
            else:
                outcomes.append(
                    StrategyEvaluationBatchVariantOutcome(
                        variant_id=variant.variant_id,
                        result=self.projection.model_copy(
                            update={"strategy_id": variant.strategy_id}
                        ),
                    )
                )
        if self.shuffle_response:
            outcomes = list(reversed(outcomes))
        yield from outcomes

    def evaluate_managed_replay(self, request: ManagedReplayRequest) -> ManagedReplayResult:
        self.managed_requests.append(request)
        return ManagedReplayResult(
            contract_version="managed_policy_replay.v1",
            decision_timing="end_of_bar_effective_next_bar",
            trade_id=request.trade_id,
            side=request.side,
            entry_time_ms=request.entry_time_ms,
            bars=(
                ManagedBarDecision(
                    time_ms=0,
                    bar_index=0,
                    phase="initial_risk",
                    bars_in_trade=1,
                    mfe_pct=Decimal("0.02"),
                    mae_pct=Decimal("0.01"),
                    active_stop_price=None,
                    active_take_profile="initial",
                    runtime_exit_rule_ids=(),
                    effective_from_time_ms=300_000,
                ),
                ManagedBarDecision(
                    time_ms=300_000,
                    bar_index=1,
                    phase="initial_risk",
                    bars_in_trade=2,
                    mfe_pct=Decimal("0.06"),
                    mae_pct=Decimal("0.01"),
                    active_stop_price=None,
                    active_take_profile="initial",
                    runtime_exit_rule_ids=(),
                    effective_from_time_ms=None,
                ),
            ),
            events=(),
            final_state={},
            raw={},
        )

    def evaluate_ema(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("not used")

    def get_composer_catalog(self, strategy_id: str) -> dict[str, Any]:
        raise AssertionError("not used")

    def validate_authoring_config(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("not used")

    def health(self) -> bool:
        return True


class FakeMarketData:
    def __init__(self, frame: MarketFrame) -> None:
        self.frame = frame
        self.requests: list[MarketRange] = []
        self.bounds_calls = 0
        self.audit_calls = 0

    def get_bounds(self, *, ticker: str, timeframe: str) -> StreamBounds:
        self.bounds_calls += 1
        return StreamBounds(
            ticker=ticker,
            timeframe=timeframe,
            earliest_open_time_ms=self.frame.market.from_ms,
            latest_open_time_ms=self.frame.market.to_ms - self.frame.market.step_ms,
            stream_state="ready",
        )

    def audit_range(self, market: MarketRange) -> ContinuityAudit:
        self.audit_calls += 1
        return ContinuityAudit(
            market=market,
            candle_count=len(self.frame.candles),
            is_continuous=True,
            stream_state="ready",
            market_data_hash="market-hash",
        )

    def read_historical_range(
        self,
        market: MarketRange,
        *,
        expected_market_data_hash: str,
    ) -> MarketFrame:
        assert expected_market_data_hash == "market-hash"
        self.requests.append(market)
        return self.frame

    def read_range(self, market: MarketRange) -> MarketFrame:
        self.requests.append(market)
        return self.frame

    def health(self) -> bool:
        return True


def test_single_instance_backtest_composes_all_layers() -> None:
    strategy = FakeStrategyEngine(strategy_projection())
    market = FakeMarketData(market_frame())
    use_case = RunSingleInstanceBacktest(strategy, market)

    outcome = use_case.execute(
        SingleInstanceBacktestRequest(
            strategy=strategy_identity(),
            range=ExplicitRange(from_ms=0, to_ms=900_000),
            execution=ExecutionPolicy(),
            accounting=AccountingPolicy(
                initial_equity=Decimal("1000"),
                entry_fee_rate=Decimal("0.001"),
                exit_fee_rate=Decimal("0.001"),
            ),
            managed_policy_enabled=False,
        )
    )
    assert outcome.managed_policy_events == ()

    assert outcome.run_id
    assert outcome.instance_id == INSTANCE_ID
    assert strategy.range_requests == [
        strategy_request().model_copy(update={"expected_market_data_hash": "market-hash"})
    ]
    assert len(strategy.range_requests) == 1  # evaluate_range_projection called exactly once
    assert market.requests == [strategy_request().market]
    assert outcome.execution.positions[0].exit_fill is not None
    assert outcome.execution.positions[0].exit_fill.candidate_type == "take_profit"
    assert outcome.accounting.realised_trade_count == 1
    assert outcome.accounting.trades[0].net_pnl == Decimal(
        "47.90209790209790209790209790"
    )
    assert outcome.accounting.final_equity == Decimal(
        "1047.902097902097902097902098"
    )
    assert strategy.managed_requests == []


def test_managed_replay_request_uses_reference_entry_price() -> None:
    strategy = FakeStrategyEngine(strategy_projection())
    use_case = RunSingleInstanceBacktest(strategy, FakeMarketData(market_frame()))

    use_case.execute(
        SingleInstanceBacktestRequest(
            strategy=strategy_identity(),
            range=ExplicitRange(from_ms=0, to_ms=900_000),
            execution=ExecutionPolicy(entry_slippage_rate=Decimal("0.01")),
        )
    )

    assert len(strategy.managed_requests) == 1
    managed = strategy.managed_requests[0]
    assert managed.trade_id == f"position:{INSTANCE_ID}:long:0"
    assert managed.entry_time_ms == 0
    assert managed.entry_price == Decimal("100")
    assert managed.strategy_spec == strategy_request().strategy_spec


def test_market_mismatch_stops_before_execution() -> None:
    mismatched = market_frame().model_copy(
        update={
            "market": MarketRange(
                ticker="ETHUSDT.P",
                timeframe="5m",
                from_ms=0,
                to_ms=900_000,
            )
        }
    )
    use_case = RunSingleInstanceBacktest(
        FakeStrategyEngine(strategy_projection()),
        FakeMarketData(mismatched),
    )

    with pytest.raises(UpstreamServiceError) as exc_info:
        use_case.execute(
            SingleInstanceBacktestRequest(
                strategy=strategy_identity(),
                range=ExplicitRange(from_ms=0, to_ms=900_000),
                managed_policy_enabled=False,
            )
        )
    assert "market identity/range" in exc_info.value.message


def test_window_resolution_failure_never_reaches_engine_or_continuation() -> None:
    # Phase-A failure (window/MDS audit), before evaluate_range_projection or
    # the continuation seam is ever entered -- proves run_id generation (now
    # owned by MaterializeBacktestProjectionOutcome) is unreachable on this
    # path.
    class DiscontinuousMarketData(FakeMarketData):
        def audit_range(self, market: MarketRange) -> ContinuityAudit:
            audit = super().audit_range(market)
            return audit.model_copy(update={"is_continuous": False, "gaps": ()})

    strategy = FakeStrategyEngine(strategy_projection())
    use_case = RunSingleInstanceBacktest(strategy, DiscontinuousMarketData(market_frame()))

    with pytest.raises(InvalidRequest, match="not continuous"):
        use_case.execute(
            SingleInstanceBacktestRequest(
                strategy=strategy_identity(),
                range=ExplicitRange(from_ms=0, to_ms=900_000),
                managed_policy_enabled=False,
            )
        )
    assert strategy.range_requests == []
    assert strategy.managed_requests == []


def test_full_available_resolved_market_reaches_every_downstream_stage() -> None:
    # full_available requests carry no range at all — only ticker/
    # base_timeframe (from the identity subset) select the stream; the
    # resolved window comes entirely from MDS bounds
    # (canonical-strategy-instance-v1, "full_available request carries no
    # range").
    resolved_market = market_frame().market
    strategy = FakeStrategyEngine(strategy_projection(market=resolved_market))
    market = FakeMarketData(market_frame())
    use_case = RunSingleInstanceBacktest(strategy, market)

    use_case.execute(
        SingleInstanceBacktestRequest(
            strategy=strategy_identity(),
            range_policy="full_available",
            execution=ExecutionPolicy(entry_slippage_rate=Decimal("0.01")),
            managed_policy_enabled=True,
        )
    )

    assert strategy.range_requests[0].market == resolved_market
    assert market.requests == [resolved_market]
    assert len(strategy.managed_requests) == 1
    assert strategy.managed_requests[0].market == resolved_market


def test_sequential_closes_compound_the_next_entry_quantity() -> None:
    market = MarketFrame(
        market=MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=1_500_000),
        candles=(
            Candle(open_time_ms=0, open="100", high="100", low="100", close="100", volume="1"),
            Candle(open_time_ms=300_000, open="100", high="106", low="100", close="105", volume="1"),
            Candle(open_time_ms=600_000, open="200", high="200", low="200", close="200", volume="1"),
            Candle(open_time_ms=900_000, open="200", high="211", low="200", close="210", volume="1"),
            Candle(open_time_ms=1_200_000, open="210", high="210", low="210", close="210", volume="1"),
        ),
        market_data_hash="sequential-hash",
    )
    leg = InitialProtectionLegDTO(
        ratio=0.05,
        attribution=ExitAttributionDTO(
            rule_id="tp", component_id="c", exit_kind="take_profit"
        ),
    )
    projection = HistoricalExecutionProjectionDTO(
        contract_version="strategy_evaluation_execution.v2",
        strategy_id="ema_pullback",
        config_hash="config-hash",
        market=market.market,
        market_data_hash="sequential-hash",
        bar_count=5,
        entry_opportunities=tuple(
            ExecutableEntryOpportunityDTO(
                bar_index=bar_index,
                side="long",
                locked_exit_profile="aligned",
                initial_stop=None,
                initial_take=leg,
            )
            for bar_index in (0, 2)
        ),
        signal_exit_events=SignalExitProjectionDTO(
            long=_EMPTY_PROFILE_EVENTS, short=_EMPTY_PROFILE_EVENTS
        ),
        warnings=(),
    )
    request = SingleInstanceBacktestRequest(
        strategy=strategy_identity(),
        range=ExplicitRange(from_ms=0, to_ms=1_500_000),
        accounting=AccountingPolicy(
            initial_equity=Decimal("1000"),
            entry_fee_rate=Decimal("0.001"),
            exit_fee_rate=Decimal("0.001"),
        ),
        managed_policy_enabled=False,
    )

    outcome = MaterializeBacktestProjectionOutcome(FakeStrategyEngine(projection)).execute(
        request, INSTANCE_ID, projection, market
    )

    first, second = outcome.accounting.trades
    assert second.equity_before == first.equity_after
    assert second.quantity == first.equity_after / (Decimal("200") * Decimal("1.001"))
    assert outcome.execution.positions[1].position.entry_fill.quantity == second.quantity
