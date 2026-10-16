"""Blocked share from a base run and the profit factor in R (OpenSpec `research-calculate-blocked-share-v1`)."""

from __future__ import annotations

import copy
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import test_optional_components as oc
import test_run_calculation as base
from test_batch_candidate_summary import trade
from test_run_calculation import _calculate, _cells, _setup, _status

from research_service.adapters.experiments.run_calculation import (
    BATCH_SIZE,
    _blocked_share,
    _chunks,
)
from research_service.application.experiments.candidate_summary import _profit_factor_r

HEADER = oc.HEADER[:-3] + ["blocked_share"] + oc.HEADER[-3:]
ROWS = [r[:-3] + [""] + r[-3:] for r in oc.ROWS]


@pytest.fixture(autouse=True)
def _table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(base, "HEADER", HEADER)
    monkeypatch.setattr(base, "ROWS", ROWS)


def _bound() -> tuple[dict[str, Any], dict[str, Any]]:
    schema, block = oc._creatable()
    schema = copy.deepcopy(schema)
    schema["metrics"].append(
        {"column": "blocked_share", "label": "Signals blocked", "format": "fraction"}
    )
    block = copy.deepcopy(block)
    block["result_bindings"]["blocked_share"] = "blocked_share"
    return schema, block


def _r(net_r: str | None):
    t = trade(Decimal("1"), Decimal("100"))
    return t.model_copy(update={"net_r_multiple": None if net_r is None else Decimal(net_r)})


def test_profit_factor_in_r():
    assert _profit_factor_r((_r("3"), _r("-1"), _r("-1"))) == Decimal("1.5")
    assert _profit_factor_r((_r("3"), _r("1"))) is None
    assert _profit_factor_r((_r("3"), _r(None), _r("-2"))) == Decimal("1.5")


def test_blocked_share_formula():
    assert _blocked_share(345, 1275) == 1 - Decimal(345) / Decimal(1275)
    assert _blocked_share(10, 0) == 0


def test_rows_with_one_base_share_one_base_candidate_and_get_the_share(tmp_path: Path) -> None:
    schema, block = _bound()
    env = _setup(tmp_path, schema=schema, materialize=block)
    job_id = _calculate(env, [oc._coords(3, 2), oc._coords(3, 4), oc._coords(3, 8)])
    status = _status(env, job_id)
    assert status["counts"] == {"published": 3}
    request = env.runner.calls[0][0]
    bases = [c for c in request.candidates if c.metadata.get("base_of_blocked_share")]
    assert len(request.candidates) == 4 and len(bases) == 1
    assert bases[0].strategy.raw_spec["stops"] == []
    after = _cells(env.table)
    shares = {
        dict(zip(after[0], r))["be_trigger_r"]: dict(zip(after[0], r))["blocked_share"]
        for r in after[-3:]
    }
    assert shares == {"2": "0.1", "4": "0.1", "8": "0.1"}
    journal = [
        json.loads(line) for line in (env.folder / "runs_calculated.jsonl").read_text().splitlines()
    ]
    base_lines = [j for j in journal if j["outcome"] == "base_run"]
    assert (
        len(base_lines) == 1
        and base_lines[0]["entry_signal_count"] == 100
        and base_lines[0]["run_id"]
    )


def test_row_with_every_option_off_is_its_own_base(tmp_path: Path) -> None:
    schema, block = _bound()
    env = _setup(tmp_path, schema=schema, materialize=block)
    _status(env, _calculate(env, [oc._coords(3)]))
    request = env.runner.calls[0][0]
    assert [c.metadata.get("base_of_blocked_share") for c in request.candidates] == [None]


def test_failed_base_fails_its_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    schema, block = _bound()
    env = _setup(tmp_path, schema=schema, materialize=block)
    real = env.runner.execute

    def drop_bases(request, **kw):
        result = real(request, **kw)
        kept = tuple(c for c in result.candidates if not c.candidate_id.startswith("b"))
        return result.model_copy(
            update={"candidates": kept, "candidate_count": len(kept), "completed_count": len(kept)}
        )

    monkeypatch.setattr(env.runner, "execute", drop_bases)
    status = _status(env, _calculate(env, [oc._coords(3, 2)]))
    assert status["counts"] == {"engine_failed": 1}
    assert "base run" in status["rows"][0]["message"]


def test_chunks_hold_rows_and_bases_within_the_batch_size():
    class R:
        def __init__(self, key):
            self.row = type("Row", (), {"base_key": key})()

    members = [R(f"k{i % 3}") for i in range(BATCH_SIZE * 2)]
    chunks = list(_chunks(members))  # type: ignore[arg-type]
    assert sum(len(c) for c in chunks) == len(members)
    for c in chunks:
        assert len(c) + len({m.row.base_key for m in c}) <= BATCH_SIZE
