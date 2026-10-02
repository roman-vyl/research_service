"""End-to-end ladder run, single and batch
(`research-frozen-partial-take-ladder-v1` task 8.1).

A recorded-style local projection (no live Engine, no market data load)
with one pct and one ATR leg in `always_on` plus one leg in the locked
`aligned` profile. On the wire both are ratios; only the attribution
`component_id` differs. Continuous market, fees 0, initial equity 10000.

Long entry at bar 0, anchor 100, Q0 = 10000 / 100 = 100:
- bar 1 reaches 101: pt_pct   20 @ 101
- bar 2 reaches 103: pt_atr   20 @ 103
- bar 3 reaches 105: pt_aligned 30 @ 105
- bar 4 reaches 108: final take closes 30 @ 108
gross = 20x1 + 20x3 + 30x5 + 30x8 = 470, average exit 104.70,
R = 470 / (100 x 5) = 0.94.

Short entry at bar 5, anchor 108, stop 1% (109.08): bar 6 hits the stop,
no leg (its 1% leg at 106.92 is never reached).
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from research_service.accounting import AccountingPolicy
from research_service.application.backtests import (
    MaterializeBacktestProjectionOutcome,
    build_backtest_request,
)
from research_service.application.experiments.candidate_summary import (
    derive_batch_candidate_summary,
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
    PartialTakeLegDTO,
    SignalExitProjectionDTO,
)
from research_service.domain.execution import ExecutionPolicy
from research_service.domain.strategy_instance import derive_strategy_instance_id
from test_batch_experiments import build_use_case, candidate, make_request
from test_single_instance_backtest import FakeMarketData, FakeStrategyEngine

STEP_MS = 300_000
CLOSES = ("100", "101.5", "103.5", "105.5", "108.5", "108", "109.5", "109.4")
TO_MS = len(CLOSES) * STEP_MS


def _frame() -> MarketFrame:
    candles = []
    previous = Decimal(CLOSES[0])
    for index, raw in enumerate(CLOSES):
        close = Decimal(raw)
        candles.append(
            Candle(
                open_time_ms=index * STEP_MS,
                open=previous,
                high=max(previous, close) + Decimal("0.2"),
                low=min(previous, close) - Decimal("0.2"),
                close=close,
                volume="1",
            )
        )
        previous = close
    return MarketFrame(
        market=MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=TO_MS),
        candles=tuple(candles),
        market_data_hash="market-hash",
    )


def _attribution(rule_id: str, kind: str, component: str) -> ExitAttributionDTO:
    return ExitAttributionDTO(rule_id=rule_id, component_id=component, exit_kind=kind)


def _leg(take_id: str, ratio: float, fraction: float, component: str) -> PartialTakeLegDTO:
    return PartialTakeLegDTO(
        take_id=take_id,
        ratio=ratio,
        fraction_of_initial=fraction,
        attribution=_attribution(take_id, "partial_take", component),
    )


def _projection() -> HistoricalExecutionProjectionDTO:
    empty: dict[str, tuple[()]] = {"aligned": (), "countertrend": (), "neutral": ()}
    return HistoricalExecutionProjectionDTO(
        contract_version="strategy_evaluation_execution.v2",
        strategy_id="ema_pullback",
        config_hash="config-hash",
        market=_frame().market,
        market_data_hash="market-hash",
        bar_count=len(CLOSES),
        entry_opportunities=(
            ExecutableEntryOpportunityDTO(
                bar_index=0,
                side="long",
                locked_exit_profile="aligned",
                initial_stop=InitialProtectionLegDTO(
                    ratio=0.05, attribution=_attribution("sl", "stop_loss", "pct_stop_loss")
                ),
                initial_take=InitialProtectionLegDTO(
                    ratio=0.08, attribution=_attribution("tp", "take_profit", "pct_take_profit")
                ),
                partial_takes=(
                    _leg("pt_pct", 0.01, 0.2, "pct_partial_take"),
                    _leg("pt_atr", 0.03, 0.2, "atr_partial_take"),
                    _leg("pt_aligned", 0.05, 0.3, "pct_partial_take"),
                ),
            ),
            ExecutableEntryOpportunityDTO(
                bar_index=5,
                side="short",
                locked_exit_profile="aligned",
                initial_stop=InitialProtectionLegDTO(
                    ratio=0.01, attribution=_attribution("sl", "stop_loss", "pct_stop_loss")
                ),
                initial_take=InitialProtectionLegDTO(
                    ratio=0.08, attribution=_attribution("tp", "take_profit", "pct_take_profit")
                ),
                partial_takes=(_leg("pt_pct", 0.01, 0.2, "pct_partial_take"),),
            ),
        ),
        signal_exit_events=SignalExitProjectionDTO(long=empty, short=empty),
        warnings=(),
    )


_ACCOUNTING = AccountingPolicy(initial_equity=Decimal("10000"))


def _selected():
    return candidate("ladder", accounting=_ACCOUNTING)


def _single_run():
    selected = _selected()
    request = build_backtest_request(
        selected.strategy,
        range=ExplicitRange(from_ms=0, to_ms=TO_MS),
        execution=ExecutionPolicy(),
        accounting=_ACCOUNTING,
        managed_policy_enabled=False,
    )
    instance_id = derive_strategy_instance_id(
        strategy_id=selected.strategy.strategy_id,
        ticker=selected.strategy.ticker,
        base_timeframe=selected.strategy.base_timeframe,
        raw_spec=selected.strategy.raw_spec,
    )
    return MaterializeBacktestProjectionOutcome(FakeStrategyEngine(_projection())).execute(
        request, instance_id, _projection(), _frame()
    )


def test_single_run_matches_hand_computed_ladder() -> None:
    outcome = _single_run()
    long_trade, short_trade = outcome.accounting.trades

    assert [(f.kind, f.take_id, f.price, f.quantity) for f in long_trade.exit_fills] == [
        ("partial_take", "pt_pct", Decimal("101.00"), Decimal("20.0")),
        ("partial_take", "pt_atr", Decimal("103.00"), Decimal("20.0")),
        ("partial_take", "pt_aligned", Decimal("105.00"), Decimal("30.0")),
        ("final", None, Decimal("108.00"), Decimal("30.0")),
    ]
    assert [f.component_id for f in long_trade.exit_fills] == [
        "pct_partial_take",
        "atr_partial_take",
        "pct_partial_take",
        "pct_take_profit",
    ]
    assert [f.bar_index for f in long_trade.exit_fills] == [1, 2, 3, 4]
    assert long_trade.quantity == Decimal("100")
    assert long_trade.gross_pnl == Decimal("470")
    assert long_trade.average_exit_price == Decimal("104.7")
    assert long_trade.gross_r_multiple == Decimal("0.94")
    assert long_trade.equity_after == Decimal("10470")

    q_short = Decimal("10470") / Decimal("108")
    assert short_trade.exit_candidate_type == "stop_loss"
    assert short_trade.exit_fills == ()
    assert short_trade.exit_price == Decimal("109.08")
    assert short_trade.quantity == q_short
    assert short_trade.gross_pnl == (Decimal("108") - Decimal("109.08")) * q_short

    reduced = [e for e in outcome.execution.events if e.event_type == "position_reduced"]
    assert [(e.bar_index, e.metadata["take_id"], e.metadata["remaining_quantity"]) for e in reduced] == [
        (1, "pt_pct", "80.0"),
        (2, "pt_atr", "60.0"),
        (3, "pt_aligned", "30.0"),
    ]
    assert outcome.accounting.final_equity == short_trade.equity_after


def test_batch_matches_the_single_run(tmp_path: Path) -> None:
    direct = _single_run()
    use_case, _ = build_use_case(
        FakeStrategyEngine(_projection()), FakeMarketData(_frame()), tmp_path
    )
    result = use_case.execute(
        make_request(_selected(), range=ExplicitRange(from_ms=0, to_ms=TO_MS))
    )
    (item,) = result.candidates
    assert item.status == "completed" and item.run_id is not None

    persisted_trades = json.loads((tmp_path / item.run_id / "trades.json").read_text())
    assert persisted_trades == [t.model_dump(mode="json") for t in direct.accounting.trades]

    summary = derive_batch_candidate_summary(direct.accounting)
    assert item.net_pnl == sum((t.net_pnl for t in direct.accounting.trades), Decimal("0"))
    assert item.gross_pnl == direct.accounting.gross_pnl
    assert item.final_equity == direct.accounting.final_equity
    assert item.realised_trade_count == 2
    assert item.cumulative_gross_r == summary.cumulative_gross_r
    assert item.return_pct == summary.return_pct
