"""Experiment manifest ``result_schema`` (research_experiment_result_schema.v1).

Describes how an Experiment's result table is read; it never holds result values.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

SCHEMA_VERSION = "research_experiment_result_schema.v1"
GRID_ID = "grid"


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class GridColumn(_Model):
    column: str
    unit: str


class Dimension(_Model):
    id: str
    label: str | None = None
    column: str | None = None
    unit: str | None = None
    grid_column: str | None = None
    grids: dict[str, GridColumn] | None = None
    # A row with an empty cell is an "off" row of this dimension (workbench switch).
    optional: bool = False

    @model_validator(mode="after")
    def _single_or_multi(self) -> Dimension:
        if self.grids:
            if not self.grid_column:
                raise ValueError(f"dimension {self.id}: grids need grid_column")
        else:
            if not self.column or not self.unit:
                raise ValueError(f"dimension {self.id}: column and unit are required")
        return self


class Metric(_Model):
    column: str
    label: str
    format: Literal["fraction", "number", "integer"]
    unit: str | None = None
    id: str | None = None

    @property
    def metric_id(self) -> str:
        return self.id or self.column


class Arms(_Model):
    column: str
    roles: dict[str, Literal["treatment", "comparison"]]
    baseline: str
    match_on: list[str]


class Provenance(_Model):
    value: str | None = None
    column: str | None = None

    @model_validator(mode="after")
    def _one(self) -> Provenance:
        if (self.value is None) == (self.column is None):
            raise ValueError("provenance needs exactly one of value or column")
        return self


class View(_Model):
    id: str
    x: str
    y: str
    controls: list[str]
    default_metric: str
    aggregate_over: list[str] | None = None
    filmstrip: str | None = None


class ResultSchema(_Model):
    contract_version: Literal["research_experiment_result_schema.v1"]
    table: str
    run_id_column: str
    provenance: Provenance
    row_columns: dict[str, str] = {}
    dimensions: list[Dimension]
    arms: Arms | None = None
    metrics: list[Metric]
    view: list[View]
