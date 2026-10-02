"""Transport-neutral contracts shared by application ports."""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from research_service.domain.errors import UpstreamServiceError


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


class ExplicitRange(BaseModel):
    """A caller-supplied `from_ms`/`to_ms` pair, without ticker/timeframe.

    Used only for `range_policy=explicit_range` requests — the strategy
    identity subset already carries `ticker`/`base_timeframe`, so this type
    intentionally does not repeat them. `range_policy=full_available`
    requests carry no range at all, not an instance of this type.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    from_ms: int = Field(ge=0)
    to_ms: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_ordering(self) -> "ExplicitRange":
        if self.from_ms >= self.to_ms:
            raise ValueError("from_ms must be less than to_ms")
        return self


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
    """Strategy Engine wire request. Internal-only since
    `canonical-strategy-instance-v1`: Research constructs this itself from a
    `StrategyInstanceIdentity` plus its own derived `instance_id`. Only
    `strategy_id`/`strategy_spec` (Engine's `raw_spec`) cross the Engine
    evaluation boundary (`strategy-evaluation-canonical-boundary-v1`);
    `instance_id` is carried here purely as Research-owned provenance so the
    Engine client can stamp it onto `StrategyEvaluationResult` — Engine
    itself never receives or echoes it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy_id: str
    instance_id: str
    strategy_spec: dict[str, object]
    market: MarketRange
    include_features: bool = True
    include_contexts: bool = True
    include_component_evidence: bool = True
    expected_market_data_hash: str | None = None


class StrategyEvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str
    strategy_id: str
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


class StrategyEvaluationBatchVariant(BaseModel):
    """One candidate's entry in a shared Strategy Engine `/range-batch`
    call. Only `strategy_id`/`strategy_spec` (Engine's `raw_spec`) and the
    ephemeral wire correlation key `variant_id` cross the Engine boundary
    (`strategy-evaluation-canonical-boundary-v1`); `instance_id` is carried
    here purely as Research-owned provenance so the Engine client can stamp
    it onto the matching `StrategyEvaluationResult` — Engine itself never
    receives or echoes it. `variant_id` equals the candidate's own
    `candidate_id` (`research-batch-experiments-v1`); it is a wire-only
    correlation key and never persisted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    variant_id: str
    instance_id: str
    strategy_id: str
    strategy_spec: dict[str, object]


class StrategyEvaluationBatchRequest(BaseModel):
    """One shared market window and N variants, evaluated by Strategy
    Engine in a single call over one shared-L0 market acquisition.
    `expected_market_data_hash` gives that shared acquisition the same
    fail-closed provenance contract single-range evaluation already has —
    Engine verifies it against the shared dataset before evaluating any
    variant, rather than trusting whatever Market Data Service returns."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    market: MarketRange
    variants: tuple[StrategyEvaluationBatchVariant, ...] = Field(min_length=1)
    expected_market_data_hash: str | None = None


class StrategyEvaluationBatchVariantOutcome(BaseModel):
    """One variant's outcome from the streamed `/range-batch` sequence
    (I8, `compact-strategy-evaluation-boundary-v1`): either a decoded
    `HistoricalExecutionProjectionDTO` (`.v2`), or an Engine-reported
    per-variant error — never both, never neither."""

    model_config = ConfigDict(frozen=True)

    variant_id: str
    result: HistoricalExecutionProjectionDTO | None = None
    error: dict[str, object] | None = None

    @model_validator(mode="after")
    def validate_exactly_one_outcome(self) -> "StrategyEvaluationBatchVariantOutcome":
        if (self.result is None) == (self.error is None):
            raise ValueError("batch variant outcome must have exactly one of result/error")
        return self


class ManagedReplayRequest(BaseModel):
    """Strategy Engine wire request. Only `strategy_id`/`strategy_spec`
    (Engine's `raw_spec`) cross the Engine boundary
    (`strategy-evaluation-canonical-boundary-v1`); managed-replay's response
    carries no instance identity, so this request needs none either."""

    model_config = ConfigDict(frozen=True)

    strategy_id: str
    strategy_spec: dict[str, object]
    market: MarketRange
    trade_id: str
    side: str
    entry_time_ms: int
    entry_price: Decimal

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


class StreamBounds(BaseModel):
    """Market Data Service's committed stream bounds for one ticker/timeframe."""

    model_config = ConfigDict(frozen=True)

    contract_version: Literal["market_stream_bounds.v1"] = "market_stream_bounds.v1"
    ticker: str
    timeframe: str
    earliest_open_time_ms: int = Field(ge=0)
    latest_open_time_ms: int = Field(ge=0)
    stream_state: str


class GapRange(BaseModel):
    model_config = ConfigDict(frozen=True)

    from_ms: int = Field(ge=0)
    to_ms: int = Field(gt=0)


class ContinuityAudit(BaseModel):
    """Market Data Service's continuity/hash audit for one market range."""

    model_config = ConfigDict(frozen=True)

    contract_version: Literal["market_continuity_audit.v1"] = "market_continuity_audit.v1"
    market: MarketRange
    candle_count: int = Field(ge=0)
    is_continuous: bool
    gaps: tuple[GapRange, ...] = ()
    stream_state: str
    market_data_hash: str | None = None


# --- HistoricalExecutionProjection consumer foundation (I3, --------------
# --- `compact-strategy-evaluation-boundary-v1`) ---------------------------
#
# Research-owned DTOs for Strategy Engine's `HistoricalExecutionProjection`
# wire contract (`strategy-research-execution-contract-v1`, I0/I1/I2 on the
# `strategy_engine` side). Deliberately NOT an import of any Strategy Engine
# Python type -- Research and Engine communicate only over HTTP/JSON; this
# is Research's own strict decoder for that JSON shape. Fail-closed
# throughout: a malformed field raises rather than being silently coerced
# or defaulted. No dense `entries[]`/`stop_ready[]`/profile arrays/SL-TP
# arrays/flattened current-profile signal arrays are reintroduced here --
# see `strategy-research-execution-contract-v1` design.md's explicit
# invariant against dense-shape contamination on this path.
#
# This module only decodes/validates/indexes -- it is not wired into the
# production historical execution loop (`execution/loop.py`) yet. That is
# I4 (locked-profile execution semantics) / I7 (route cutover).

_EXIT_PROFILES: tuple[str, ...] = ("aligned", "countertrend", "neutral")


class ExitAttributionDTO(BaseModel):
    """Shared attribution shape across every historical execution fact.
    Canonical `exit_kind` values: `stop_loss` (on `initial_stop`),
    `take_profit` (on `initial_take`), `signal` (on a signal-exit
    candidate), `partial_take` (only on a `partial_takes` leg). No `layer`
    field on the wire -- Research derives the canonical constant
    `exit_layer = "exit_policy"` downstream (I4), it is not carried here."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(min_length=1)
    component_id: str = Field(min_length=1)
    exit_kind: Literal["stop_loss", "take_profit", "signal", "partial_take"]


class InitialProtectionLegDTO(BaseModel):
    """One resolved, attributed protection leg (stop or take) at an entry
    opportunity's bar. Ratio must be finite -- Engine never emits a bare
    ratio without attribution, and this decoder never fabricates one."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ratio: float
    attribution: ExitAttributionDTO

    @field_validator("ratio")
    @classmethod
    def validate_ratio_is_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("initial protection leg ratio must be finite")
        return value


class PartialTakeLegDTO(BaseModel):
    """One frozen partial take leg (`research-partial-take-execution-v1`
    "Partial take decoding"): close `fraction_of_initial` of the initial
    quantity at `anchor x (1 +/- ratio)`. `take_id` is the Engine rule's
    `instance_id` and equals `attribution.rule_id`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    take_id: str = Field(min_length=1)
    ratio: float
    fraction_of_initial: float
    attribution: ExitAttributionDTO

    @field_validator("ratio")
    @classmethod
    def validate_ratio(cls, value: float) -> float:
        if not math.isfinite(value) or value <= 0:
            raise ValueError("partial take ratio must be finite and positive")
        return value

    @field_validator("fraction_of_initial")
    @classmethod
    def validate_fraction(cls, value: float) -> float:
        if not math.isfinite(value) or not 0 < value < 1:
            raise ValueError("partial take fraction_of_initial must be in (0, 1)")
        return value

    @model_validator(mode="after")
    def validate_attribution(self) -> "PartialTakeLegDTO":
        if self.attribution.exit_kind != "partial_take":
            raise ValueError("partial take attribution must have exit_kind partial_take")
        if self.attribution.rule_id != self.take_id:
            raise ValueError("partial take take_id must equal attribution.rule_id")
        return self


class ExecutableEntryOpportunityDTO(BaseModel):
    """`entry_allowed AND protection_ready`, collapsed by Engine --
    `stop_ready` never exists as its own field on this contract.
    `initial_stop`/`initial_take` are independently nullable: a strategy
    MAY be take-only or stop-only for the active `always_on`+profile
    combination (`strategy-research-execution-contract-v1`)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bar_index: int = Field(ge=0)
    side: Literal["long", "short"]
    locked_exit_profile: str
    initial_stop: InitialProtectionLegDTO | None
    initial_take: InitialProtectionLegDTO | None
    # Absent on the wire when there are no legs, and omitted again on dump
    # so artifacts without legs stay byte-identical (design D4).
    partial_takes: tuple[PartialTakeLegDTO, ...] = ()

    @field_validator("locked_exit_profile")
    @classmethod
    def validate_locked_exit_profile(cls, value: str) -> str:
        if value not in _EXIT_PROFILES:
            raise ValueError(f"unsupported locked_exit_profile: {value!r}")
        return value

    @model_validator(mode="after")
    def validate_leg_attribution_kinds(self) -> "ExecutableEntryOpportunityDTO":
        if self.initial_stop is not None and self.initial_stop.attribution.exit_kind != "stop_loss":
            raise ValueError("initial_stop attribution must have exit_kind stop_loss")
        if self.initial_take is not None and self.initial_take.attribution.exit_kind != "take_profit":
            raise ValueError("initial_take attribution must have exit_kind take_profit")
        take_ids = [leg.take_id for leg in self.partial_takes]
        if len(set(take_ids)) != len(take_ids):
            raise ValueError("partial take take_id values must be unique")
        fractions = sum(
            (Decimal(str(leg.fraction_of_initial)) for leg in self.partial_takes), Decimal("0")
        )
        if fractions >= 1:
            raise ValueError("partial take fractions must sum below 1")
        return self

    @model_serializer(mode="wrap")
    def _omit_empty_partial_takes(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, object]:
        data: dict[str, object] = handler(self)
        if not self.partial_takes:
            data.pop("partial_takes", None)
        return data


class SignalExitCandidateDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    attribution: ExitAttributionDTO

    @model_validator(mode="after")
    def validate_signal_kind(self) -> "SignalExitCandidateDTO":
        if self.attribution.exit_kind != "signal":
            raise ValueError("signal-exit candidate attribution must have exit_kind signal")
        return self


class SignalExitEventDTO(BaseModel):
    """`candidates` is preserved in Engine's own canonical declared order
    (always_on rules first, then the locked profile's own rules, each in
    their declared list order) and never flattened to a single bool or a
    single winning candidate -- I2 proved multiple rules can fire
    simultaneously; winner selection is a Research execution-semantics
    concern (I4), not a decode-time concern."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bar_index: int = Field(ge=0)
    candidates: tuple[SignalExitCandidateDTO, ...] = Field(min_length=1)


class SignalExitProjectionDTO(BaseModel):
    """Per-side, per-profile sparse event lists. Both sides carry exactly
    the three canonical profiles as keys (even when a profile's own event
    list is empty) -- a caller holding a locked profile looks up only that
    profile's own list, never a flattened current-bar-profile series."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    long: dict[str, tuple[SignalExitEventDTO, ...]]
    short: dict[str, tuple[SignalExitEventDTO, ...]]

    @field_validator("long", "short")
    @classmethod
    def validate_profile_keys(
        cls, value: dict[str, tuple[SignalExitEventDTO, ...]]
    ) -> dict[str, tuple[SignalExitEventDTO, ...]]:
        if set(value) != set(_EXIT_PROFILES):
            raise ValueError(
                f"signal exit projection must have exactly the profile keys {_EXIT_PROFILES}, "
                f"got {sorted(value)}"
            )
        for profile, events in value.items():
            bar_indices = [event.bar_index for event in events]
            if bar_indices != sorted(bar_indices) or len(set(bar_indices)) != len(bar_indices):
                raise ValueError(
                    f"signal exit events for profile {profile!r} must be strictly ordered "
                    "by unique bar_index"
                )
        return value


class ManagedConditionSeriesDTO(BaseModel):
    """Pre-confirm boolean condition, both sides, one entry per bar
    (`historical-managed-projection-v1`). No confirm-bars window
    applied -- Research applies that itself, entry-anchored, via
    `build_managed_policy_timeline_from_projection`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    long: tuple[bool, ...]
    short: tuple[bool, ...]


TradeMetric = Literal["bars_since_entry", "mfe_pct", "mfe_distance", "mfe_r"]


class ManagedTransitionThresholdDTO(BaseModel):
    """Trade-state quantity `trade_metric` >= `distances[distance_id][i]`
    (null -> False) (`composite-managed-phase-condition-v1` design D6)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    distance_id: str = Field(min_length=1)
    trade_metric: TradeMetric


class ManagedTransitionTermDTO(BaseModel):
    """One `at_least` term: exactly one of `condition_id` (market) or
    (`distance_id`, `trade_metric`) (trade threshold)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    condition_id: str | None = None
    distance_id: str | None = None
    trade_metric: TradeMetric | None = None

    @model_validator(mode="after")
    def validate_exactly_one_reference(self) -> "ManagedTransitionTermDTO":
        has_condition = self.condition_id is not None
        has_distance = self.distance_id is not None and self.trade_metric is not None
        has_partial_distance = (self.distance_id is None) != (self.trade_metric is None)
        if has_condition == has_distance or has_partial_distance:
            raise ValueError(
                "at_least term must set exactly one of condition_id or "
                "(distance_id, trade_metric)"
            )
        return self


class ManagedTransitionAtLeastDTO(BaseModel):
    """At least `k` of `terms` true."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    k: int = Field(ge=1)
    terms: tuple[ManagedTransitionTermDTO, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_k_within_terms(self) -> "ManagedTransitionAtLeastDTO":
        if self.k > len(self.terms):
            raise ValueError("at_least k must not exceed the number of terms")
        return self


class ManagedTransitionPathDTO(BaseModel):
    """True on a bar iff `condition_id` (if any) is true for the trade
    side, every threshold holds and `at_least` (if any) holds."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path_id: str = Field(min_length=1)
    condition_id: str | None = None
    thresholds: tuple[ManagedTransitionThresholdDTO, ...] = ()
    at_least: ManagedTransitionAtLeastDTO | None = None


class ManagedPhaseTransitionRuleDTO(BaseModel):
    """Exactly one of `condition_id`, (`distance_id`, `trade_metric`) or
    `paths` is set -- never two, never none. `paths` is the generic form
    of a composite phase condition: the rule fires on the first true path
    in order (`historical-managed-projection-cutover-v1` design D1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["phase_transition"]
    rule_id: str = Field(min_length=1)
    target_phase: str = Field(min_length=1)
    condition_id: str | None = None
    distance_id: str | None = None
    trade_metric: TradeMetric | None = None
    paths: tuple[ManagedTransitionPathDTO, ...] | None = None

    @model_validator(mode="after")
    def validate_exactly_one_reference(self) -> "ManagedPhaseTransitionRuleDTO":
        has_condition = self.condition_id is not None
        has_distance = self.distance_id is not None and self.trade_metric is not None
        has_partial_distance = (self.distance_id is None) != (self.trade_metric is None)
        has_paths = self.paths is not None
        if has_paths and not self.paths:
            raise ValueError("phase_transition paths must not be empty")
        if has_partial_distance or (has_condition + has_distance + has_paths) != 1:
            raise ValueError(
                "phase_transition rule must set exactly one of condition_id, "
                "(distance_id, trade_metric) or paths"
            )
        return self


class ManagedTakeActionRuleDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["take_action"]
    rule_id: str = Field(min_length=1)
    activation_phase: str
    resulting_profile: str = Field(min_length=1)


class ManagedStopActionRuleDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["stop_action"]
    rule_id: str = Field(min_length=1)
    activation_phase: str
    distance_id: str = Field(min_length=1)


class ManagedRuntimeExitRuleDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["runtime_exit"]
    rule_id: str = Field(min_length=1)
    activation_phase: str
    condition_id: str = Field(min_length=1)
    confirm_bars: int = Field(ge=1)
    exit_class: Literal["runtime_protective", "runtime_take", "runtime_close"]


class HistoricalManagedProjectionDTO(BaseModel):
    """Research-owned decode of Strategy Engine's
    `HistoricalManagedProjection` (`historical-managed-projection-v1`).
    Every identifier here is opaque -- Research dispatches on
    `rules[].kind` (and each variant's own closed enum) alone, never on
    a `component_id` or raw strategy parameter (none exists on this
    contract to read)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    conditions: dict[str, ManagedConditionSeriesDTO]
    distances: dict[str, tuple[float | None, ...]]
    rules: tuple[
        Annotated[
            ManagedPhaseTransitionRuleDTO
            | ManagedTakeActionRuleDTO
            | ManagedStopActionRuleDTO
            | ManagedRuntimeExitRuleDTO,
            Field(discriminator="kind"),
        ],
        ...,
    ]

    @model_validator(mode="after")
    def validate_references_exist(self) -> "HistoricalManagedProjectionDTO":
        """Every `condition_id`/`distance_id` a rule, path, threshold or
        term names must exist, so a malformed contract fails decode
        instead of raising `KeyError` mid-execution."""

        condition_ids: set[str] = set()
        distance_ids: set[str] = set()
        for rule in self.rules:
            if rule.kind == "phase_transition":
                if rule.condition_id is not None:
                    condition_ids.add(rule.condition_id)
                if rule.distance_id is not None:
                    distance_ids.add(rule.distance_id)
                for path in rule.paths or ():
                    if path.condition_id is not None:
                        condition_ids.add(path.condition_id)
                    distance_ids.update(item.distance_id for item in path.thresholds)
                    for term in path.at_least.terms if path.at_least is not None else ():
                        if term.condition_id is not None:
                            condition_ids.add(term.condition_id)
                        if term.distance_id is not None:
                            distance_ids.add(term.distance_id)
            elif rule.kind == "stop_action":
                distance_ids.add(rule.distance_id)
            elif rule.kind == "runtime_exit":
                condition_ids.add(rule.condition_id)
        missing_conditions = sorted(condition_ids - self.conditions.keys())
        missing_distances = sorted(distance_ids - self.distances.keys())
        if missing_conditions or missing_distances:
            raise ValueError(
                "managed projection references unknown ids: "
                f"conditions={missing_conditions}, distances={missing_distances}"
            )
        return self


class HistoricalExecutionProjectionDTO(BaseModel):
    """Research-owned decode of Strategy Engine's
    `HistoricalExecutionProjection` (`strategy-research-execution-
    contract-v1`), superseding the shipped sparse `StrategyDecisionEvent`
    contract (`strategy_evaluation_execution.v1`) with
    `strategy_evaluation_execution.v2` -- same envelope family
    (`contract_version`/`strategy_id`/`config_hash`/`market{...}`/
    `warnings`, matching `strategy_engine/adapters/http/
    strategy_serialization.py`'s real wire shape), new payload shape.
    Deliberately carries no `raw` field -- unlike the legacy
    `StrategyEvaluationResult`, this DTO does not retain the original
    response body (`compact-strategy-evaluation-boundary-v1` I3:
    "raw=body retention removed" on this path).

    `market_data_hash`/`bar_count` live on THIS DTO (Research's own flat
    shape, matching `StrategyEvaluationResult`'s convention), NOT nested
    under `market` -- the real Engine envelope nests them inside
    `market{...}` alongside `base_timeframe` (see
    `strategy_serialization.py::serialize_strategy_evaluation_execution`);
    `parse_historical_execution_projection` is responsible for that
    translation, the same way `_parse_evaluation_result` already
    translates `market.base_timeframe` into `MarketRange.timeframe` for
    the legacy contract. This DTO's own shape does not need to mirror
    the wire's nesting to be a correct decode of it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: Literal["strategy_evaluation_execution.v2"]
    strategy_id: str = Field(min_length=1)
    config_hash: str = Field(min_length=1)
    market: MarketRange
    market_data_hash: str = Field(min_length=1)
    bar_count: int = Field(ge=0)
    entry_opportunities: tuple[ExecutableEntryOpportunityDTO, ...]
    signal_exit_events: SignalExitProjectionDTO
    warnings: tuple[str, ...] = ()
    managed: HistoricalManagedProjectionDTO | None = None

    @model_validator(mode="after")
    def validate_bar_indices_in_range(self) -> "HistoricalExecutionProjectionDTO":
        for opportunity in self.entry_opportunities:
            if opportunity.bar_index >= self.bar_count:
                raise ValueError(
                    f"entry opportunity bar_index {opportunity.bar_index} is outside "
                    f"[0, {self.bar_count})"
                )
        for side_events in (self.signal_exit_events.long, self.signal_exit_events.short):
            for events in side_events.values():
                for event in events:
                    if event.bar_index >= self.bar_count:
                        raise ValueError(
                            f"signal exit event bar_index {event.bar_index} is outside "
                            f"[0, {self.bar_count})"
                        )
        return self

    @model_validator(mode="after")
    def validate_no_duplicate_entry_opportunities(self) -> "HistoricalExecutionProjectionDTO":
        seen: set[tuple[int, str]] = set()
        for opportunity in self.entry_opportunities:
            key = (opportunity.bar_index, opportunity.side)
            if key in seen:
                raise ValueError(
                    f"duplicate entry opportunity for bar_index={opportunity.bar_index} "
                    f"side={opportunity.side!r}"
                )
            seen.add(key)
        return self

    @model_validator(mode="after")
    def validate_no_simultaneous_long_and_short_entry(self) -> "HistoricalExecutionProjectionDTO":
        """Mirrors `strategy_engine`'s I1 corrective-pass fail-loud
        invariant (`historical_execution_projection.py`): a strategy
        producing both a long and a short executable entry opportunity on
        the same bar is an internal inconsistency, not a valid dual-
        opportunity bar. Checked again here, defense-in-depth, since
        Research decodes this contract independently over HTTP and must
        not trust the wire to have preserved Engine's own invariant."""

        long_bars = {o.bar_index for o in self.entry_opportunities if o.side == "long"}
        short_bars = {o.bar_index for o in self.entry_opportunities if o.side == "short"}
        overlap = long_bars & short_bars
        if overlap:
            raise ValueError(
                "simultaneous long and short entry opportunity at bar_index(es): "
                f"{sorted(overlap)}"
            )
        return self


class StrategyDiagnosticEvaluationDTO(BaseModel):
    """Research-owned decode of Strategy Engine's separate dense diagnostic
    contract (`strategy_diagnostic_evaluation.v1`, unaffected by I7's
    `/range` cutover -- `POST /strategy-evaluations/range/diagnostics`
    keeps serving this shape). Used only to build a run's separately
    persisted diagnostic artifact
    (`research-diagnostics-projection-v1`), never as execution input.
    Field content (`features`/`contexts`/`potential_entries`/
    `component_evidence`) is passed through as opaque dicts -- this
    module does not need typed access to their internals, only to
    forward them to the diagnostics projection layer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: Literal["strategy_diagnostic_evaluation.v1"]
    strategy_id: str = Field(min_length=1)
    config_hash: str = Field(min_length=1)
    market: MarketRange
    market_data_hash: str = Field(min_length=1)
    bar_count: int = Field(ge=0)
    features: dict[str, object]
    contexts: dict[str, object]
    potential_entries: dict[str, object]
    component_evidence: dict[str, object]
    warnings: tuple[str, ...] = ()


def validate_projection_alignment(
    projection: HistoricalExecutionProjectionDTO,
    *,
    expected_market: MarketRange,
    expected_market_data_hash: str,
    expected_bar_count: int,
) -> None:
    """Fail-closed alignment check between a decoded projection and
    Research's own request/MarketFrame context. Kept as a standalone
    function (not folded into the DTO's own validators, which only know
    the response body) so the future execution loop calls this once at
    load time instead of re-deriving alignment checks itself
    (`strategy-research-execution-contract-v1`: "the loop rejects the run
    rather than executing against mismatched data"). The projection
    carries no dense `time_ms[]` -- `bar_index` joins back to Research's
    own `MarketFrame` for actual timestamps; this function does not
    require or accept one."""

    if projection.market != expected_market:
        raise UpstreamServiceError(
            service="strategy_engine",
            status_code=502,
            message="Strategy Engine projection market identity/range does not match the request",
            details={
                "expected_market": expected_market.model_dump(),
                "projection_market": projection.market.model_dump(),
            },
        )
    if projection.market_data_hash != expected_market_data_hash:
        raise UpstreamServiceError(
            service="strategy_engine",
            status_code=502,
            message="Strategy Engine projection market_data_hash does not match the request",
            details={
                "expected_market_data_hash": expected_market_data_hash,
                "projection_market_data_hash": projection.market_data_hash,
            },
        )
    if projection.bar_count != expected_bar_count:
        raise UpstreamServiceError(
            service="strategy_engine",
            status_code=502,
            message="Strategy Engine projection bar_count does not match the request",
            details={
                "expected_bar_count": expected_bar_count,
                "projection_bar_count": projection.bar_count,
            },
        )


class HistoricalExecutionProjectionIndex:
    """Immutable, once-built lookup foundation over a validated
    `HistoricalExecutionProjectionDTO`. Built once at load time so a
    future execution loop never linearly scans sparse event arrays per
    bar (`strategy-research-execution-contract-v1` I3). Read-only: no
    method mutates the index or the projection it was built from."""

    __slots__ = ("_projection", "_entry_by_bar_and_side", "_signal_event_by_side_profile_bar")

    def __init__(self, projection: HistoricalExecutionProjectionDTO) -> None:
        self._projection = projection
        entry_by_bar_and_side: dict[tuple[int, str], ExecutableEntryOpportunityDTO] = {}
        for opportunity in projection.entry_opportunities:
            entry_by_bar_and_side[(opportunity.bar_index, opportunity.side)] = opportunity
        self._entry_by_bar_and_side = entry_by_bar_and_side

        signal_event_by_side_profile_bar: dict[tuple[str, str, int], SignalExitEventDTO] = {}
        for side, side_events in (
            ("long", projection.signal_exit_events.long),
            ("short", projection.signal_exit_events.short),
        ):
            for profile, events in side_events.items():
                for event in events:
                    signal_event_by_side_profile_bar[(side, profile, event.bar_index)] = event
        self._signal_event_by_side_profile_bar = signal_event_by_side_profile_bar

    @classmethod
    def build(cls, projection: HistoricalExecutionProjectionDTO) -> "HistoricalExecutionProjectionIndex":
        return cls(projection)

    @property
    def projection(self) -> HistoricalExecutionProjectionDTO:
        return self._projection

    def lookup_entry(self, bar_index: int, side: str) -> ExecutableEntryOpportunityDTO | None:
        """O(1) lookup, never a scan of `entry_opportunities`."""

        return self._entry_by_bar_and_side.get((bar_index, side))

    def lookup_signal_event(
        self, side: str, profile: str, bar_index: int
    ) -> SignalExitEventDTO | None:
        """O(1) lookup, never a scan of `signal_exit_events[side][profile]`.
        Returns `None` on an empty/no-fire bar, matching the projection's
        own sparse representation -- callers distinguish "no event" from
        "event with zero candidates" (which the DTO layer already forbids:
        `SignalExitEventDTO.candidates` requires at least one)."""

        return self._signal_event_by_side_profile_bar.get((side, profile, bar_index))
