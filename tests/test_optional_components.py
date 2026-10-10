"""Optional components in the materialize block: empty cell = off, filled = on."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import test_run_calculation as base
from pydantic import ValidationError
from test_run_calculation import BASE, _calculate, _cells, _plan, _setup, _status

from research_service.domain.experiment_materialize import MaterializeBlock

HEADER = ["width", "lookback", "sl", "tp", "be_trigger_r", "be_lock_r", "return_pct", "trades", "profit_factor",
          "run_id", "provenance", "market_data_hash"]
ROWS = [
    [3, 20, 3.0, 9.0, "", "", "0.25", 100, "1.5", "", "replay", "h1"],     # 0: option off
    [3, 20, 3.0, 9.0, "6", "0", "0.25", 100, "1.5", "", "replay", "h1"],   # 1: same cell, option on
    [4, 20, 3.0, 9.0, "6", "", "0.3", 70, "1.4", "", "replay", "h1"],      # 2: lock missing
    [5, 20, 3.0, 9.0, "6", "y", "0.3", 70, "1.4", "", "replay", "h1"],     # 3: unparsable lock
]

ITEM = {"component_id": "initial_r_lock_stop", "instance_id": "be", "params": {"trigger_r": 0, "lock_r": 0}}
OPTION = {
    "id": "break_even",
    "column": "be_trigger_r",
    "insert": {
        "path": "/raw_spec/stops",
        "item": ITEM,
        "bindings": [
            {"column": "be_trigger_r", "path": "/params/trigger_r", "type": "number"},
            {"column": "be_lock_r", "path": "/params/lock_r", "type": "number"},
        ],
    },
}


def _schema() -> dict[str, Any]:
    schema = copy.deepcopy(base.SCHEMA)
    schema["dimensions"].append(
        {"id": "be", "label": "Breakeven", "column": "be_trigger_r", "unit": "R", "optional": True}
    )
    return schema


def _materialize(*options: dict[str, Any]) -> dict[str, Any]:
    block = copy.deepcopy(base.MATERIALIZE)
    block["strategy_template"]["raw_spec"]["stops"] = []
    block["options"] = list(options)
    return block


@pytest.fixture(autouse=True)
def _table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(base, "HEADER", HEADER)
    monkeypatch.setattr(base, "ROWS", ROWS)


def _spec_hash(width: float, lookback: int, stops: list[dict[str, Any]]) -> str:
    raw = copy.deepcopy(base.MATERIALIZE["strategy_template"]["raw_spec"])
    raw["setup"].update(min_width=float(width), lookback=lookback)
    raw["exits"].update(sl=3.0, tp=9.0)
    raw["stops"] = stops
    return hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()


def _coords(width: float, be: float | None = None) -> dict[str, Any]:
    coords: dict[str, Any] = {"width": width, "lookback": 20, "sl": 3.0}
    if be is not None:
        coords["be"] = be
    return {"coords": coords}


def test_off_row_equals_template_and_on_row_carries_the_item(tmp_path: Path) -> None:
    env = _setup(tmp_path, schema=_schema(), materialize=_materialize(OPTION))
    plan = _plan(env, [_coords(3), _coords(3, 6)])
    off, on = plan["rows"]
    assert (off["status"], on["status"]) == ("calculable", "calculable")
    assert off["config_hash"] == _spec_hash(3, 20, [])
    item = copy.deepcopy(ITEM)
    item["params"] = {"trigger_r": 6.0, "lock_r": 0.0}
    assert on["config_hash"] == _spec_hash(3, 20, [item])


def test_rows_with_an_empty_optional_cell_are_addressable(tmp_path: Path) -> None:
    env = _setup(tmp_path, schema=_schema(), materialize=_materialize(OPTION))
    plan = _plan(env, [_coords(3), {"coords": {"width": 3, "lookback": 20, "sl": 3.0, "be": ""}}])
    assert [r["status"] for r in plan["rows"]] == ["calculable", "calculable"]
    assert plan["rows"][0]["config_hash"] == plan["rows"][1]["config_hash"]


def test_half_filled_option_is_inconsistent_not_off(tmp_path: Path) -> None:
    env = _setup(tmp_path, schema=_schema(), materialize=_materialize(OPTION))
    row = _plan(env, [_coords(4, 6)])["rows"][0]
    assert (row["status"], row["reason"]) == ("skipped", "option_inconsistent")


def test_unparsable_option_cell_skips_the_row(tmp_path: Path) -> None:
    env = _setup(tmp_path, schema=_schema(), materialize=_materialize(OPTION))
    row = _plan(env, [_coords(5, 6)])["rows"][0]
    assert (row["status"], row["reason"]) == ("skipped", "binding_value_invalid")
    assert "be_lock_r" in row["message"]


def test_option_column_must_be_an_optional_dimension(tmp_path: Path) -> None:
    schema = _schema()
    schema["dimensions"][-1]["optional"] = False
    env = _setup(tmp_path, schema=schema, materialize=_materialize(OPTION))
    resp = env.client.post(f"{BASE}/runs/calculate-plan", json={"rows": [_coords(3)]})
    assert resp.status_code >= 400
    assert "optional dimension" in resp.text


def test_block_validation() -> None:
    template = base.MATERIALIZE["strategy_template"]
    block = copy.deepcopy(base.MATERIALIZE)
    block["options"] = [OPTION]
    with pytest.raises(ValidationError, match="not a list|does not exist"):
        MaterializeBlock.model_validate(block)  # template has no /raw_spec/stops list
    block["strategy_template"] = {**template, "raw_spec": {**template["raw_spec"], "stops": []}}
    MaterializeBlock.model_validate(block)
    twice = copy.deepcopy(block)
    twice["options"] = [OPTION, OPTION]
    with pytest.raises(ValidationError, match="option ids must be unique"):
        MaterializeBlock.model_validate(twice)
    bad_item = copy.deepcopy(block)
    bad_item["options"][0]["insert"]["bindings"][0]["path"] = "/params/missing"
    with pytest.raises(ValidationError, match="does not exist"):
        MaterializeBlock.model_validate(bad_item)


def test_one_column_may_feed_several_paths() -> None:
    block = _materialize()
    block["bindings"].append({"column": "sl", "path": "/raw_spec/trigger/lookback", "type": "integer"})
    MaterializeBlock.model_validate(block)
    block["bindings"].append({"column": "tp", "path": "/raw_spec/trigger/lookback", "type": "number"})
    with pytest.raises(ValidationError, match="binding paths must be unique"):
        MaterializeBlock.model_validate(block)


def test_surface_without_options_is_unchanged(tmp_path: Path) -> None:
    env = _setup(tmp_path, schema=_schema(), materialize=_materialize())
    row = _plan(env, [_coords(3)])["rows"][0]
    assert row["config_hash"] == _spec_hash(3, 20, [])


# --- a coordinate without a row ----------------------------------------------------------

BREAK_EVEN = {
    "id": "break_even",
    "column": "be_trigger_r",
    "insert": {
        "path": "/raw_spec/stops",
        "item": ITEM,
        "bindings": [{"column": "be_trigger_r", "path": "/params/trigger_r", "type": "number"}],
    },
}


def _creatable() -> tuple[dict[str, Any], dict[str, Any]]:
    """Schema with declared BE values and a block whose every binding is a dimension column."""
    schema = _schema()
    schema["dimensions"][-1]["values"] = [2, 3, 4, 6, 8, 10]
    block = _materialize(BREAK_EVEN)
    block["bindings"] = [b for b in block["bindings"] if b["column"] != "tp"]
    return schema, block


def test_coordinate_without_a_row_is_calculable_as_a_new_row(tmp_path: Path) -> None:
    schema, block = _creatable()
    env = _setup(tmp_path, schema=schema, materialize=block)
    row = _plan(env, [_coords(3, 8)])["rows"][0]
    assert (row["status"], row["new_row"]) == ("calculable", True)
    item = copy.deepcopy(ITEM)
    item["params"] = {"trigger_r": 8.0, "lock_r": 0}
    raw = copy.deepcopy(base.MATERIALIZE["strategy_template"]["raw_spec"])
    raw["setup"].update(min_width=3.0, lookback=20)
    raw["exits"].update(sl=3.0)
    raw["stops"] = [item]
    assert row["config_hash"] == hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()


def test_calculate_appends_the_new_row(tmp_path: Path) -> None:
    schema, block = _creatable()
    env = _setup(tmp_path, schema=schema, materialize=block)
    before = _cells(env.table)
    job_id = _calculate(env, [_coords(3, 8)])
    status = _status(env, job_id)
    assert status["counts"] == {"published": 1}
    after = _cells(env.table)
    assert after[: len(before)] == before  # existing rows untouched
    assert len(after) == len(before) + 1
    new = dict(zip(after[0], after[-1]))
    assert (new["width"], new["lookback"], new["sl"], new["be_trigger_r"]) == ("3", "20", "3", "8")
    assert new["run_id"].startswith("run_") and new["provenance"] == "engine"
    assert new["be_lock_r"] == "" and new["tp"] == ""
    # the same coordinates are a row now
    assert _plan(env, [_coords(3, 8)])["rows"][0]["reason"] == "has_run"


def test_value_outside_the_declared_values_is_not_allowed(tmp_path: Path) -> None:
    schema, block = _creatable()
    env = _setup(tmp_path, schema=schema, materialize=block)
    row = _plan(env, [_coords(3, 5)])["rows"][0]
    assert (row["status"], row["reason"]) == ("skipped", "coord_not_allowed")


def test_bound_column_outside_the_coordinates_is_not_creatable(tmp_path: Path) -> None:
    env = _setup(tmp_path, schema=_schema(), materialize=_materialize(OPTION))  # `tp` is not a dimension
    row = _plan(env, [_coords(99)])["rows"][0]
    assert (row["status"], row["reason"]) == ("skipped", "row_not_creatable")
    assert "tp" in row["message"]
