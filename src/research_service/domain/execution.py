"""Transport-neutral execution domain contracts."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from research_service.domain.contracts import MarketRange

from pydantic import BaseModel, ConfigDict, Field, model_validator

ExecutionSide = Literal["long", "short"]


class ExecutionPolicy(BaseModel):
    """Execution assumptions owned by Research Service.

    Entry fills support explicit adverse slippage. Initial stop/take levels
    are always anchored to the signal-bar close -- the original BBB v1
    engine's VectorBT/managed-loop anchor, not a caller-selectable profile;
    there is no other supported anchor. Fees are intentionally deferred to
    accounting.
    """

    model_config = ConfigDict(frozen=True)

    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    entry_slippage_rate: Decimal = Field(default=Decimal("0"), ge=0, lt=1)
    entry_price_source: Literal["signal_bar_close"] = "signal_bar_close"
    protection_anchor: Literal["signal_bar_close"] = "signal_bar_close"


class EntryDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    instance_id: str = Field(min_length=1)
    side: ExecutionSide
    bar_index: int = Field(ge=0)
    time_ms: int = Field(ge=0)
    reference_price: Decimal = Field(gt=0)


class EntryFill(BaseModel):
    model_config = ConfigDict(frozen=True)

    fill_id: str = Field(min_length=1)
    instance_id: str = Field(min_length=1)
    side: ExecutionSide
    bar_index: int = Field(ge=0)
    time_ms: int = Field(ge=0)
    reference_price: Decimal = Field(gt=0)
    fill_price: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    slippage_rate: Decimal = Field(ge=0, lt=1)


class InitialProtection(BaseModel):
    """Initial static stop/take policy resolved at the entry bar."""

    model_config = ConfigDict(frozen=True)

    side: ExecutionSide
    source_bar_index: int = Field(ge=0)
    source_time_ms: int = Field(ge=0)
    anchor_price: Decimal = Field(gt=0)
    stop_loss_ratio: Decimal | None = Field(default=None, ge=0)
    take_profit_ratio: Decimal | None = Field(default=None, ge=0)
    stop_loss_price: Decimal | None = Field(default=None, gt=0)
    take_profit_price: Decimal | None = Field(default=None, gt=0)
    ready: Literal[True] = True

    @model_validator(mode="after")
    def validate_side_of_levels(self) -> "InitialProtection":
        if self.side == "long":
            if self.stop_loss_price is not None and self.stop_loss_price > self.anchor_price:
                raise ValueError("long stop loss must not exceed its anchor")
            if self.take_profit_price is not None and self.take_profit_price < self.anchor_price:
                raise ValueError("long take profit must not be below its anchor")
        else:
            if self.stop_loss_price is not None and self.stop_loss_price < self.anchor_price:
                raise ValueError("short stop loss must not be below its anchor")
            if self.take_profit_price is not None and self.take_profit_price > self.anchor_price:
                raise ValueError("short take profit must not exceed its anchor")
        return self


class ExitCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_type: Literal[
        "stop_loss",
        "managed_stop",
        "take_profit",
        "runtime_protective",
        "runtime_take",
        "runtime_close",
        "runtime_exit",
        "signal",
    ]
    layer: Literal["exit_policy", "exit_management"] = "exit_policy"
    bar_index: int = Field(ge=0)
    time_ms: int = Field(ge=0)
    reference_level: Decimal = Field(gt=0)
    fill_price: Decimal = Field(gt=0)
    reason: str = Field(min_length=1)
    rule_id: str | None = None
    component_id: str | None = None
    exit_kind: str | None = None


class ExitArbitrationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    same_bar_policy: Literal["v1"] = "v1"
    winner: ExitCandidate | None
    losing_candidates: tuple[ExitCandidate, ...] = ()


class ExitFill(BaseModel):
    model_config = ConfigDict(frozen=True)

    fill_id: str = Field(min_length=1)
    position_id: str = Field(min_length=1)
    instance_id: str = Field(min_length=1)
    side: ExecutionSide
    candidate_type: Literal[
        "stop_loss",
        "managed_stop",
        "take_profit",
        "runtime_protective",
        "runtime_take",
        "runtime_close",
        "runtime_exit",
        "signal",
    ]
    bar_index: int = Field(ge=0)
    time_ms: int = Field(ge=0)
    reference_level: Decimal = Field(gt=0)
    fill_price: Decimal = Field(gt=0)
    reason: str = Field(min_length=1)
    layer: Literal["exit_policy", "exit_management"] = "exit_policy"
    rule_id: str | None = None
    component_id: str | None = None
    exit_kind: str | None = None


class PositionState(BaseModel):
    model_config = ConfigDict(frozen=True)

    position_id: str = Field(min_length=1)
    instance_id: str = Field(min_length=1)
    side: ExecutionSide
    status: Literal["open"] = "open"
    entry_fill: EntryFill
    initial_protection: InitialProtection

    @model_validator(mode="after")
    def validate_consistency(self) -> "PositionState":
        if self.entry_fill.instance_id != self.instance_id:
            raise ValueError("entry fill belongs to another instance")
        if self.entry_fill.side != self.side:
            raise ValueError("entry fill side differs from position side")
        if self.initial_protection.side != self.side:
            raise ValueError("initial protection side differs from position side")
        if self.initial_protection.source_bar_index != self.entry_fill.bar_index:
            raise ValueError("initial protection must come from the entry bar")
        return self


class ExecutionEvent(BaseModel):
    """Deterministic execution-layer event emitted by the bar loop."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(min_length=1)
    event_type: Literal[
        "entry_filled",
        "exit_filled",
        "position_left_open",
    ]
    instance_id: str = Field(min_length=1)
    position_id: str = Field(min_length=1)
    side: ExecutionSide
    bar_index: int = Field(ge=0)
    time_ms: int = Field(ge=0)
    fill_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class PositionExecution(BaseModel):
    """Execution facts for one position, before fees/PnL accounting."""

    model_config = ConfigDict(frozen=True)

    position: PositionState
    status: Literal["open", "closed"]
    exit_fill: ExitFill | None = None
    exit_arbitration: ExitArbitrationResult | None = None

    @model_validator(mode="after")
    def validate_status(self) -> "PositionExecution":
        if self.status == "closed":
            if self.exit_fill is None or self.exit_arbitration is None:
                raise ValueError("closed execution requires exit fill and arbitration")
            if self.exit_fill.position_id != self.position.position_id:
                raise ValueError("exit fill belongs to another position")
            if self.exit_fill.instance_id != self.position.instance_id:
                raise ValueError("exit fill belongs to another instance")
            if self.exit_fill.side != self.position.side:
                raise ValueError("exit fill side differs from position side")
        else:
            if self.exit_fill is not None or self.exit_arbitration is not None:
                raise ValueError("open execution cannot contain an exit")
        return self


class ExecutionLoopResult(BaseModel):
    """Transport-neutral output of the unified bar-by-bar execution loop."""

    model_config = ConfigDict(frozen=True)

    contract_version: Literal["research_execution_loop.v1"] = "research_execution_loop.v1"
    instance_id: str = Field(min_length=1)
    market: MarketRange
    positions: tuple[PositionExecution, ...]
    events: tuple[ExecutionEvent, ...]
    final_open_position: PositionState | None = None

    @model_validator(mode="after")
    def validate_result(self) -> "ExecutionLoopResult":
        if any(item.position.instance_id != self.instance_id for item in self.positions):
            raise ValueError("execution result contains another strategy instance")
        entry_indices = [item.position.entry_fill.bar_index for item in self.positions]
        if entry_indices != sorted(entry_indices):
            raise ValueError("positions must be ordered by entry bar")
        open_items = [item for item in self.positions if item.status == "open"]
        if len(open_items) > 1:
            raise ValueError("execution loop may leave at most one position open")
        if self.final_open_position is None:
            if open_items:
                raise ValueError("open execution requires final_open_position")
        else:
            if len(open_items) != 1:
                raise ValueError("final_open_position requires one open execution")
            if open_items[0].position.position_id != self.final_open_position.position_id:
                raise ValueError("final open position differs from open execution")
        return self
