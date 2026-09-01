"""Independent old-BBB/vectorbt-grounded sizing and accounting parity gate.

The reference below mirrors vectorbt's order-processing resource equations,
not Research's sizing/accounting helpers. In vectorbt ``execute_order_nb``, an
infinite short amount becomes 100% (``Percent``); ``buy_nb`` caps a long by
cash including fees, while ``sell_nb`` independently caps a 100% short from
free cash using ``adjusted_price * (1 + fees)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from research_service.accounting import AccountingPolicy
from research_service.application.backtests import (
    MaterializeBacktestProjectionOutcome,
    SingleInstanceBacktestRequest,
)
from research_service.domain.contracts import (
    Candle,
    ExecutableEntryOpportunityDTO,
    ExitAttributionDTO,
    ExplicitRange,
    HistoricalExecutionProjectionDTO,
    InitialProtectionLegDTO,
    MarketFrame,
    MarketRange,
    SignalExitProjectionDTO,
)
from research_service.domain.execution import ExecutionPolicy
from research_service.domain.strategy_instance import (
    StrategyInstanceIdentity,
    derive_strategy_instance_id,
)

ZERO = Decimal("0")
ONE = Decimal("1")
EMPTY_EVENTS = {"aligned": (), "countertrend": (), "neutral": ()}


@dataclass(frozen=True)
class ReferenceTrade:
    quantity: Decimal
    entry_notional: Decimal
    entry_fee: Decimal
    exit_notional: Decimal
    exit_fee: Decimal
    gross_pnl: Decimal
    net_pnl: Decimal
    equity_after: Decimal


def _vectorbt_inf_reference(
    *,
    side: str,
    equity: Decimal,
    reference_entry_price: Decimal,
    exit_fill_price: Decimal,
    entry_slippage_rate: Decimal,
    entry_fee_rate: Decimal,
    exit_fee_rate: Decimal,
) -> ReferenceTrade:
    """Execute one independent ``size=np.inf`` reference trade.

    The long and short branches are deliberately separate so this fixture
    cannot establish short parity merely by reusing the long formula.
    Fixed fees are zero, matching the canonical change assumptions.
    """

    if side == "long":
        adjusted_entry = reference_entry_price * (ONE + entry_slippage_rate)
        # vectorbt buy_nb: max_req_cash = cash_limit / (1 + fees)
        max_required_cash = equity / (ONE + entry_fee_rate)
        quantity = max_required_cash / adjusted_entry
        gross_pnl = (exit_fill_price - adjusted_entry) * quantity
    else:
        adjusted_entry = reference_entry_price * (ONE - entry_slippage_rate)
        # vectorbt execute_order_nb: -inf -> 100% resources; sell_nb:
        # max_short_size = total_free_cash / (adj_price * (1 + fees)).
        total_free_cash = equity
        quantity = total_free_cash / (adjusted_entry * (ONE + entry_fee_rate))
        gross_pnl = (adjusted_entry - exit_fill_price) * quantity

    entry_notional = adjusted_entry * quantity
    entry_fee = entry_notional * entry_fee_rate
    exit_notional = exit_fill_price * quantity
    exit_fee = exit_notional * exit_fee_rate
    net_pnl = gross_pnl - entry_fee - exit_fee
    return ReferenceTrade(
        quantity=quantity,
        entry_notional=entry_notional,
        entry_fee=entry_fee,
        exit_notional=exit_notional,
        exit_fee=exit_fee,
        gross_pnl=gross_pnl,
        net_pnl=net_pnl,
        equity_after=equity + net_pnl,
    )


def test_canonical_long_short_compounding_matches_vectorbt_inf_reference() -> None:
    market_range = MarketRange(
        ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=1_500_000
    )
    market = MarketFrame(
        market=market_range,
        candles=(
            Candle(open_time_ms=0, open="100", high="101", low="99", close="100", volume="1"),
            Candle(open_time_ms=300_000, open="102", high="106", low="101", close="105", volume="1"),
            Candle(open_time_ms=600_000, open="200", high="201", low="199", close="200", volume="1"),
            Candle(open_time_ms=900_000, open="198", high="199", low="189", close="190", volume="1"),
            Candle(open_time_ms=1_200_000, open="190", high="191", low="189", close="190", volume="1"),
        ),
        market_data_hash="vectorbt-parity-hash",
    )
    take = InitialProtectionLegDTO(
        ratio=0.05,
        attribution=ExitAttributionDTO(
            rule_id="tp", component_id="reference", exit_kind="take_profit"
        ),
    )
    projection = HistoricalExecutionProjectionDTO(
        contract_version="strategy_evaluation_execution.v2",
        strategy_id="ema_pullback",
        config_hash="vectorbt-reference",
        market=market_range,
        market_data_hash="vectorbt-parity-hash",
        bar_count=5,
        entry_opportunities=(
            ExecutableEntryOpportunityDTO(
                bar_index=0,
                side="long",
                locked_exit_profile="aligned",
                initial_stop=None,
                initial_take=take,
            ),
            ExecutableEntryOpportunityDTO(
                bar_index=2,
                side="short",
                locked_exit_profile="aligned",
                initial_stop=None,
                initial_take=take,
            ),
        ),
        signal_exit_events=SignalExitProjectionDTO(
            long=EMPTY_EVENTS, short=EMPTY_EVENTS
        ),
        warnings=(),
    )
    identity = StrategyInstanceIdentity(
        strategy_id="ema_pullback",
        ticker="BTCUSDT.P",
        base_timeframe="5m",
        raw_spec={"anchor": {"period": 200}},
    )
    execution_policy = ExecutionPolicy(entry_slippage_rate=Decimal("0.01"))
    accounting_policy = AccountingPolicy(
        initial_equity=Decimal("10000"),
        entry_fee_rate=Decimal("0.001"),
        exit_fee_rate=Decimal("0.002"),
    )
    request = SingleInstanceBacktestRequest(
        strategy=identity,
        range=ExplicitRange(from_ms=0, to_ms=1_500_000),
        execution=execution_policy,
        accounting=accounting_policy,
        managed_policy_enabled=False,
    )
    instance_id = derive_strategy_instance_id(
        strategy_id=identity.strategy_id,
        ticker=identity.ticker,
        base_timeframe=identity.base_timeframe,
        raw_spec=identity.raw_spec,
    )

    outcome = MaterializeBacktestProjectionOutcome(object()).execute(  # type: ignore[arg-type]
        request, instance_id, projection, market
    )

    long_reference = _vectorbt_inf_reference(
        side="long",
        equity=accounting_policy.initial_equity,
        reference_entry_price=Decimal("100"),
        exit_fill_price=Decimal("105"),
        entry_slippage_rate=execution_policy.entry_slippage_rate,
        entry_fee_rate=accounting_policy.entry_fee_rate,
        exit_fee_rate=accounting_policy.exit_fee_rate,
    )
    short_reference = _vectorbt_inf_reference(
        side="short",
        equity=long_reference.equity_after,
        reference_entry_price=Decimal("200"),
        exit_fill_price=Decimal("190"),
        entry_slippage_rate=execution_policy.entry_slippage_rate,
        entry_fee_rate=accounting_policy.entry_fee_rate,
        exit_fee_rate=accounting_policy.exit_fee_rate,
    )

    for actual, expected in zip(
        outcome.accounting.trades,
        (long_reference, short_reference),
        strict=True,
    ):
        assert actual.quantity == expected.quantity
        assert actual.entry_notional == expected.entry_notional
        assert actual.entry_fee == expected.entry_fee
        assert actual.exit_notional == expected.exit_notional
        assert actual.exit_fee == expected.exit_fee
        assert actual.gross_pnl == expected.gross_pnl
        assert actual.net_pnl == expected.net_pnl
        assert actual.equity_after == expected.equity_after

    assert outcome.accounting.trades[1].equity_before == long_reference.equity_after
    assert outcome.accounting.final_equity == short_reference.equity_after
