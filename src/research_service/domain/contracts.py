"""Transport-neutral contracts shared by application ports."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_TIMEFRAME_MS = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}


def timeframe_ms(timeframe: str) -> int:
    try:
        return _TIMEFRAME_MS[timeframe]
    except KeyError as exc:
        raise ValueError(f"unsupported timeframe: {timeframe}") from exc


class MarketRange(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticker: str = Field(pattern=r"^[A-Z0-9]+\.P$")
    timeframe: str
    from_ms: int = Field(ge=0)
    to_ms: int = Field(gt=0)

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, value: str) -> str:
        if value not in _TIMEFRAME_MS:
            raise ValueError(f"unsupported timeframe: {value}")
        return value

    @model_validator(mode="after")
    def validate_range(self) -> "MarketRange":
        if self.from_ms >= self.to_ms:
            raise ValueError("from_ms must be less than to_ms")
        step = _TIMEFRAME_MS[self.timeframe]
        if self.from_ms % step or self.to_ms % step:
            raise ValueError("range boundaries must align to timeframe")
        return self

    @property
    def step_ms(self) -> int:
        return _TIMEFRAME_MS[self.timeframe]


class Candle(BaseModel):
    model_config = ConfigDict(frozen=True)

    open_time_ms: int = Field(ge=0)
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


class MarketFrame(BaseModel):
    model_config = ConfigDict(frozen=True)

    market: MarketRange
    candles: tuple[Candle, ...]
    market_data_hash: str | None = None

    @model_validator(mode="after")
    def validate_grid(self) -> "MarketFrame":
        expected_count = (self.market.to_ms - self.market.from_ms) // self.market.step_ms
        if len(self.candles) != expected_count:
            raise ValueError("market frame is incomplete")
        expected = self.market.from_ms
        for candle in self.candles:
            if candle.open_time_ms != expected:
                raise ValueError("market frame is gapped or unordered")
            expected += self.market.step_ms
        return self


class StrategyEvaluationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy_id: str
    strategy_version: str = "v1"
    instance_id: str
    strategy_spec: dict[str, object]
    market: MarketRange
    compatibility_profile: str = "bbb_v1"
    include_features: bool = True
    include_contexts: bool = True
    include_component_evidence: bool = True
    expected_market_data_hash: str | None = None


class StrategyEvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str
    strategy_id: str
    strategy_version: str
    instance_id: str
    config_hash: str
    market: MarketRange
    bar_count: int = Field(ge=0)
    market_data_hash: str
    time_ms: tuple[int, ...]
    entries: dict[str, tuple[bool, ...]]
    exit_policy: dict[str, object]
    component_evidence: dict[str, object]
    raw: dict[str, object]

    @model_validator(mode="after")
    def validate_decision_grid(self) -> "StrategyEvaluationResult":
        if self.contract_version != "strategy_evaluation.v1":
            raise ValueError("unsupported Strategy Engine evaluation contract")
        expected_count = (self.market.to_ms - self.market.from_ms) // self.market.step_ms
        if self.bar_count != expected_count or len(self.time_ms) != expected_count:
            raise ValueError("strategy evaluation does not cover the requested market grid")
        expected = self.market.from_ms
        for value in self.time_ms:
            if value != expected:
                raise ValueError("strategy evaluation timestamps are gapped or unordered")
            expected += self.market.step_ms
        for side, values in self.entries.items():
            if side not in {"long", "short"}:
                raise ValueError("strategy evaluation contains an unsupported side")
            if len(values) != expected_count:
                raise ValueError("entry decision length does not match market grid")
        return self


class ManagedReplayRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy_id: str
    strategy_version: str = "v1"
    instance_id: str
    strategy_spec: dict[str, object]
    market: MarketRange
    trade_id: str
    side: str
    entry_time_ms: int
    entry_price: Decimal
    compatibility_profile: str = "bbb_v1"

    @field_validator("side")
    @classmethod
    def validate_side(cls, value: str) -> str:
        if value not in {"long", "short"}:
            raise ValueError("side must be long or short")
        return value


class ManagedBarDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    time_ms: int
    bar_index: int = Field(ge=0)
    phase: str
    bars_in_trade: int = Field(ge=1)
    mfe_pct: Decimal
    mae_pct: Decimal
    active_stop_price: Decimal | None
    active_take_profile: str
    runtime_exit_rule_ids: tuple[str, ...]
    effective_from_time_ms: int | None


class ManagedReplayResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str
    decision_timing: str
    trade_id: str
    side: str
    entry_time_ms: int
    bars: tuple[ManagedBarDecision, ...]
    events: tuple[dict[str, object], ...]
    final_state: dict[str, object]
    raw: dict[str, object]

    @model_validator(mode="after")
    def validate_timing(self) -> "ManagedReplayResult":
        if self.contract_version != "managed_policy_replay.v1":
            raise ValueError("unsupported managed policy replay contract")
        if self.decision_timing != "end_of_bar_effective_next_bar":
            raise ValueError("unsupported managed decision timing")
        for index, bar in enumerate(self.bars[:-1]):
            if bar.effective_from_time_ms != self.bars[index + 1].time_ms:
                raise ValueError("managed decision effective time is inconsistent")
        if self.bars and self.bars[-1].effective_from_time_ms is not None:
            raise ValueError("last managed decision must not claim an unavailable next bar")
        return self
