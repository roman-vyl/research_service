"""Experiment manifest ``materialize`` block (research_experiment_materialize.v1).

The block is the machine-readable definition of what an Experiment studies: a
complete strategy template, the row columns bound into it, the run-summary fields
bound back to the row's metric columns, and the Research policy. Research Service
copies values along JSON Pointers; it never interprets the strategy.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from research_service.accounting.contracts import AccountingPolicy
from research_service.domain.contracts import ExplicitRange
from research_service.domain.execution import ExecutionPolicy
from research_service.domain.strategy_instance import DeployableStrategyInstance

MATERIALIZE_VERSION = "research_experiment_materialize.v1"


class Binding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    column: str = Field(min_length=1)
    path: str = Field(pattern=r"^/")
    type: Literal["number", "integer", "string"]


class ResearchPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    range_policy: Literal["explicit_range", "full_available"] = "explicit_range"
    range: ExplicitRange | None = None
    execution: ExecutionPolicy = ExecutionPolicy()
    accounting: AccountingPolicy = AccountingPolicy()
    managed_policy_enabled: bool = True

    @model_validator(mode="after")
    def _range_matches_policy(self) -> ResearchPolicy:
        if self.range_policy == "explicit_range" and self.range is None:
            raise ValueError("range_policy=explicit_range requires range")
        if self.range_policy == "full_available" and self.range is not None:
            raise ValueError("range_policy=full_available must not include a range")
        return self


class MaterializeBlock(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["research_experiment_materialize.v1"]
    strategy_template: DeployableStrategyInstance
    bindings: tuple[Binding, ...] = Field(min_length=1)
    result_bindings: dict[str, str] = Field(min_length=1)
    research_policy: ResearchPolicy

    @model_validator(mode="after")
    def _paths_exist(self) -> MaterializeBlock:
        document = self.strategy_template.model_dump(mode="json")
        columns = [b.column for b in self.bindings]
        if len(columns) != len(set(columns)):
            raise ValueError("binding columns must be unique")
        paths = [b.path for b in self.bindings]
        if len(paths) != len(set(paths)):
            raise ValueError("binding paths must be unique")
        for binding in self.bindings:
            if pointer_parts(binding.path)[:1] in (["enabled"], ["strategy_id"]):
                raise ValueError(f"binding {binding.column}: {binding.path} is not bindable")
            pointer_get(document, binding.path)
        return self


def pointer_parts(path: str) -> list[str]:
    if not path.startswith("/"):
        raise ValueError(f"not a JSON Pointer: {path!r}")
    return [p.replace("~1", "/").replace("~0", "~") for p in path[1:].split("/")]


def _step(node: Any, part: str, path: str) -> tuple[Any, Any]:
    if isinstance(node, dict):
        if part not in node:
            raise ValueError(f"path {path} does not exist in the template")
        return node, part
    if isinstance(node, list):
        if not part.isdigit() or int(part) >= len(node):
            raise ValueError(f"path {path} does not exist in the template")
        return node, int(part)
    raise ValueError(f"path {path} does not exist in the template")


def pointer_get(document: Any, path: str) -> Any:
    node = document
    for part in pointer_parts(path):
        container, key = _step(node, part, path)
        node = container[key]
    return node


def pointer_set(document: Any, path: str, value: Any) -> None:
    parts = pointer_parts(path)
    node = document
    for part in parts[:-1]:
        container, key = _step(node, part, path)
        node = container[key]
    container, key = _step(node, parts[-1], path)
    container[key] = value
