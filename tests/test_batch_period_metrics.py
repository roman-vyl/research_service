"""Period, yearly and trade-average metrics of a batch candidate (OpenSpec `research-run-period-metrics-v1`)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from test_batch_candidate_summary import accounting, trade

from research_service.application.experiments.candidate_summary import (
    DEFAULT_PERIOD_SPLIT_MS,
    derive_batch_candidate_summary,
    derive_period_fields,
)
from research_service.application.experiments.contracts import BatchCandidateResult

E = Decimal("10000")


def ms(year: int, month: int = 1, day: int = 1) -> int:
    return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp() * 1000)


def chain(*items: tuple[float, int]) -> tuple:
    """Trades with the given returns on the running equity and exit times, compounded from E."""
    out, equity = [], E
    for i, (ret, exit_ms) in enumerate(items):
        net = equity * Decimal(str(ret))
        out.append(
            trade(net, equity, trade_id=f"t{i}").model_copy(
                update={"exit_time_ms": exit_ms, "entry_time_ms": exit_ms}
            )
        )
        equity += net
    return tuple(out)


def test_default_split_is_2023_07_01():
    assert DEFAULT_PERIOD_SPLIT_MS == ms(2023, 7, 1)


def test_each_part_compounds_from_the_initial_equity():
    trades = chain((0.10, ms(2022, 3)), (-0.05, ms(2023, 2)), (0.20, ms(2024, 5)))
    f = derive_period_fields(trades, E)
    assert f["is_net_pnl"] == Decimal("450.00") and f["is_trades"] == 2
    assert f["oos_net_pnl"] == Decimal("2000.0") and f["oos_trades"] == 1
    assert f["period_split_ms"] == DEFAULT_PERIOD_SPLIT_MS


def test_trade_on_the_split_instant_is_out_of_sample():
    trades = chain((0.10, DEFAULT_PERIOD_SPLIT_MS - 1), (0.10, DEFAULT_PERIOD_SPLIT_MS))
    f = derive_period_fields(trades, E)
    assert (f["is_trades"], f["oos_trades"]) == (1, 1)


def test_custom_split():
    trades = chain((0.10, ms(2022, 3)), (0.10, ms(2024, 3)))
    f = derive_period_fields(trades, E, ms(2025))
    assert (f["is_trades"], f["oos_trades"], f["oos_net_pnl"]) == (2, 0, 0)


def test_years_over_the_account_chain_and_years_without_trades():
    trades = chain((0.10, ms(2022, 3)), (0.25, ms(2024, 2)), (-0.20, ms(2024, 9)))
    f = derive_period_fields(trades, E)
    assert set(f["years"]) == {"2022", "2024"}
    assert f["years"]["2022"].return_pct == Decimal("0.1") and f["years"]["2022"].trades == 1
    assert f["years"]["2024"].return_pct == Decimal("0") and f["years"]["2024"].trades == 2
    assert f["years_up"] == 1 and f["worst_year"] == Decimal("0")


def test_year_is_the_utc_exit_year():
    trades = chain((0.10, ms(2024) - 1))  # 2023-12-31T23:59:59.999Z
    assert set(derive_period_fields(trades, E)["years"]) == {"2023"}


def test_trade_averages():
    trades = chain(
        (0.02, ms(2022)), (-0.01, ms(2022, 2)), (0.04, ms(2022, 3)), (-0.01, ms(2022, 4))
    )
    f = derive_period_fields(trades, E)
    assert f["avg_trade_bp"] == pytest.approx(Decimal("100"))
    assert f["payoff_ratio"] == pytest.approx(Decimal("3"))


@pytest.mark.parametrize("returns", [(0.01, 0.02), (-0.01, -0.02)])
def test_payoff_is_null_without_winners_or_losers(returns):
    trades = chain(*((r, ms(2022, i + 1)) for i, r in enumerate(returns)))
    f = derive_period_fields(trades, E)
    assert f["payoff_ratio"] is None and f["avg_trade_bp"] is not None


def test_no_trades():
    f = derive_period_fields((), E)
    assert (f["is_net_pnl"], f["is_trades"], f["oos_net_pnl"], f["oos_trades"]) == (0, 0, 0, 0)
    assert f["years"] == {} and f["years_up"] == 0 and f["worst_year"] is None
    assert f["avg_trade_bp"] is None and f["payoff_ratio"] is None


def test_summary_carries_the_fields_into_a_candidate_result():
    trades = chain((0.10, ms(2022, 3)), (0.20, ms(2024, 5)))
    summary = derive_batch_candidate_summary(accounting(trades, E))
    result = BatchCandidateResult(
        candidate_id="c",
        run_id="run_x",
        instance_id="i",
        status="completed",
        return_pct=summary.return_pct,
        max_drawdown=summary.max_drawdown,
        long=summary.long,
        short=summary.short,
        **summary.period_fields,
    )
    dumped = result.model_dump(mode="python")
    assert dumped["years"]["2024"]["return_pct"] == Decimal("0.2") and dumped["years_up"] == 2


def test_failed_candidate_must_not_carry_period_fields():
    with pytest.raises(ValueError):
        BatchCandidateResult(candidate_id="c", instance_id="i", status="failed", years_up=1)


def test_summary_written_before_the_fields_still_validates():
    summary = derive_batch_candidate_summary(accounting(chain((0.1, ms(2022))), E))
    BatchCandidateResult(
        candidate_id="c",
        run_id="run_x",
        instance_id="i",
        status="completed",
        return_pct=summary.return_pct,
        max_drawdown=summary.max_drawdown,
        long=summary.long,
        short=summary.short,
    )


def test_result_binding_paths_resolve_year_and_period_fields():
    from research_service.adapters.experiments.run_calculation import _lookup

    trades = chain((0.10, ms(2022, 3)), (0.20, ms(2024, 5)))
    summary = derive_batch_candidate_summary(accounting(trades, E))
    dumped = BatchCandidateResult(
        candidate_id="c",
        run_id="run_x",
        instance_id="i",
        status="completed",
        return_pct=summary.return_pct,
        max_drawdown=summary.max_drawdown,
        long=summary.long,
        short=summary.short,
        **summary.period_fields,
    ).model_dump(mode="python")
    assert _lookup(dumped, "years.2024.return_pct") == Decimal("0.2")
    assert _lookup(dumped, "years.2023.return_pct") is None
    assert _lookup(dumped, "is_net_pnl") == Decimal("1000.0")
