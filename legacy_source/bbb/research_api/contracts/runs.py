"""Run report contracts — mirror ``research/results`` JSON schema v3/v4."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SUPPORTED_REPORT_SCHEMA_VERSIONS: frozenset[int] = frozenset({3, 4, 5, 6})


class TradeOverlay(BaseModel):
    """Chart overlay fields for one trade (subset of trade record)."""

    model_config = ConfigDict(extra="forbid")

    trade_id: int | str
    direction: Literal["long", "short"]
    status: Literal["open", "closed"]
    entry_time_ms: int
    exit_time_ms: int | None
    entry_price: float | None
    exit_price: float | None
    exit_reason: str


class BreakEvenDiagnostics(BaseModel):
    """Exit-management combiner output for ``break_even_stop`` (managed path)."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    instance_id: str
    trigger_r: float
    trigger_price: float | None = None
    triggered: bool
    trigger_time_ms: int | None = None
    stop_moved_to: float | None = None
    initial_stop_price: float
    initial_risk: float
    active_stop_management_source: Literal["profile", "always_on"]


ManagedTradeManagementEventType = Literal[
    "phase_changed",
    "active_stop_updated",
    "active_take_updated",
    "runtime_exit_triggered",
    "exit_rule_triggered",
    "exit_executed",
]


class TradeManagementEvent(BaseModel):
    """Runtime trace event from trade-management (schema v6; diagnostic + managed)."""

    model_config = ConfigDict(extra="forbid")

    trade_id: str
    time_ms: int | None = None
    bar_index: int
    side: Literal["long", "short"]
    event_type: ManagedTradeManagementEventType
    from_phase: str | None = None
    to_phase: str | None = None
    rule_id: str | None = None
    component_id: str | None = None
    price: float | None = None
    stop_price: float | None = None
    mfe_pct: float | None = None
    mae_pct: float | None = None
    bars_in_trade: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TradeManagementDiagnostics(BaseModel):
    """Trade-management runtime block on closed trades (schema v6; diagnostic + managed)."""

    model_config = ConfigDict(extra="forbid")

    phase_at_exit: str
    max_phase_reached: str
    active_stop_source_at_exit: str | None = None
    active_stop_price_at_exit: float | None = None
    exit_layer: str | None = None
    exit_owner: str | None = None
    exit_rule_id: str | None = None
    exit_component_id: str | None = None
    best_price_before_exit: float | None = None
    giveback_from_best_price_pct: float | None = None
    capture_ratio: float | None = None
    mfe_pct: float | None = None
    bars_to_proven: int | None = None
    bars_to_protected: int | None = None
    bars_to_runner: int | None = None
    mfe_at_proven_pct: float | None = None
    mfe_at_protected_pct: float | None = None
    mfe_at_runner_pct: float | None = None
    active_stop_at_exit: float | None = None
    active_take_at_exit: str | None = None
    active_stop_component_id: str | None = None
    active_take_component_id: str | None = None
    exit_candidate_type: str | None = None
    managed_events: list[TradeManagementEvent] | None = None


class TradeRecord(TradeOverlay):
    model_config = ConfigDict(extra="forbid")

    size: float | None
    pnl: float | None
    return_pct: float | None
    entry_profile: str | None = None
    entry_context_state: str | None = None
    entry_context_consumption: dict[str, Any] | None = None
    exit_context_consumption: dict[str, Any] | None = None
    active_exit_profile: str | None = None
    exit_group: str | None = None
    exit_profile: str | None = None
    exit_component_id: str | None = None
    exit_instance_id: str | None = None
    exit_kind: str | None = None
    gross_pnl: float | None = None
    fees_paid: float | None = None
    gross_return_pct: float | None = None
    hold_bars: int | None = None
    hold_minutes: int | None = None
    mfe_price: float | None = None
    mfe_pct: float | None = None
    mfe_atr: float | None = None
    mae_price: float | None = None
    mae_pct: float | None = None
    mae_atr: float | None = None
    bars_to_mfe: int | None = None
    bars_to_mae: int | None = None
    captured_price: float | None = None
    captured_pct: float | None = None
    captured_atr: float | None = None
    capture_ratio: float | None = None
    giveback_price: float | None = None
    giveback_pct: float | None = None
    giveback_atr: float | None = None
    bars_from_mfe_to_exit: int | None = None
    quality_flags: list[str] | None = None
    path_diagnostics: dict[str, Any] | None = None
    reference_levels: dict[str, Any] | None = None
    entry_setup_diagnostics: dict[str, dict[str, Any]] = Field(default_factory=dict)
    entry_idx: int | None = None
    exit_idx: int | None = None
    break_even: BreakEvenDiagnostics | None = None
    exit_layer: str | None = None
    managed_exit_candidate_type: str | None = None
    trade_management: TradeManagementDiagnostics | None = None


class SideMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trades: int
    pnl: float
    return_pct: float
    profit_factor: float | None
    win_rate: float | None


class TotalMetrics(SideMetrics):
    model_config = ConfigDict(extra="forbid")

    sharpe: float
    max_drawdown: float


class OpenTradesMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    long: int
    short: int
    total: int


class DiagnosticBucketMetrics(BaseModel):
    """v4 profile / exit_reason breakdown bucket (not ``SideMetrics``)."""

    model_config = ConfigDict(extra="forbid")

    trades: int
    pnl: float
    gross_pnl: float
    fees_paid: float
    profit_factor: float | None
    win_rate: float | None
    avg_return_pct: float | None
    avg_hold_bars: float | None


class ProfileBucketMetrics(DiagnosticBucketMetrics):
    model_config = ConfigDict(extra="forbid")

    exit_reason_mix: dict[str, int] = Field(default_factory=dict)


class ProfileSideSection(BaseModel):
    """One side (or total) slice of ``profile_side_breakdown``."""

    model_config = ConfigDict(extra="forbid")

    aligned: ProfileBucketMetrics
    countertrend: ProfileBucketMetrics
    neutral: ProfileBucketMetrics
    total: ProfileBucketMetrics


class ProfileSideBreakdown(BaseModel):
    """Closed-trade aggregates by direction × HTF entry profile."""

    model_config = ConfigDict(extra="forbid")

    long: ProfileSideSection
    short: ProfileSideSection
    total: ProfileSideSection


class ExitReasonBucketMetrics(DiagnosticBucketMetrics):
    model_config = ConfigDict(extra="forbid")


class FeeDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_fees_paid: float
    gross_pnl: float
    net_pnl: float
    fees_rate: float
    fees_as_pct_of_gross_profit: float | None = None


class QualityFlagBucketMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trades: int
    avg_mfe_atr: float | None
    avg_mfe_pct: float | None
    avg_capture_ratio: float | None
    avg_giveback_atr: float | None
    avg_giveback_pct: float | None
    exit_reason_mix: dict[str, int] = Field(default_factory=dict)


class ExitComponentQualityBucketMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trades: int
    avg_mfe_atr: float | None
    avg_mfe_pct: float | None
    avg_capture_ratio: float | None
    avg_giveback_atr: float | None
    avg_giveback_pct: float | None
    quality_flag_mix: dict[str, int] = Field(default_factory=dict)
    signal_exit_winners: int
    signal_exit_giveback_failures: int


class VariantMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    long: SideMetrics
    short: SideMetrics
    total: TotalMetrics
    open_trades: OpenTradesMetrics
    profile_breakdown: dict[str, ProfileBucketMetrics] | None = None
    profile_side_breakdown: ProfileSideBreakdown | None = None
    exit_reason_breakdown: dict[str, ExitReasonBucketMetrics] | None = None
    fee_diagnostics: FeeDiagnostics | None = None
    quality_flag_breakdown: dict[str, QualityFlagBucketMetrics] | None = None
    exit_component_quality_breakdown: dict[str, ExitComponentQualityBucketMetrics] | None = None
    path_diagnostics_summary: dict[str, Any] | None = None
    trade_management_summary: dict[str, Any] | None = None
    baseline_vs_managed_summary: dict[str, Any] | None = None


class PathDiagnosticsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_: str = Field(alias="schema")
    version: str
    window: str
    open_trades: str
    same_bar_level_policy: str
    post_exit_bars: str


class TradeQualityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_: str = Field(alias="schema")
    high_mfe_atr: float
    high_mfe_pct_fallback: float
    high_capture_ratio: float
    low_capture_ratio: float
    low_mfe_atr: float
    low_mfe_pct_fallback: float
    giveback_failure_atr: float
    atr_source: str | None = None


class DataRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_open_time_ms: int
    to_open_time_ms: int


class RunVariant(BaseModel):
    model_config = ConfigDict(extra="allow")

    variant: str
    config_id: str
    symbol: str
    timeframe: str
    strategy_spec: dict[str, Any]
    metrics: VariantMetrics
    component_counters: list[Any] = Field(default_factory=list)
    trade_records: list[TradeRecord]
    trade_management_events: list[TradeManagementEvent] | None = None

    @property
    def trade_overlays(self) -> list[TradeOverlay]:
        return [
            TradeOverlay(
                trade_id=t.trade_id,
                direction=t.direction,
                status=t.status,
                entry_time_ms=t.entry_time_ms,
                exit_time_ms=t.exit_time_ms,
                entry_price=t.entry_price,
                exit_price=t.exit_price,
                exit_reason=t.exit_reason,
            )
            for t in self.trade_records
        ]


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    created_at: str
    family: str
    symbol: str
    timeframe: str


class RunCompactVariant(BaseModel):
    """Compact run summary variant projection without per-trade arrays."""

    model_config = ConfigDict(extra="ignore")

    variant: str
    config_id: str
    symbol: str
    timeframe: str
    strategy_spec: dict[str, Any]
    metrics: VariantMetrics
    component_counters: list[Any] = Field(default_factory=list)
    trade_records_count: int | None = None
    closed_trades_count: int | None = None
    open_trades_count: int | None = None


class RunReport(BaseModel):
    model_config = ConfigDict(extra="allow")

    run_id: str
    created_at: str
    report_schema_version: int
    family: str
    symbol: str
    timeframe: str
    candles: int
    data_range: DataRange
    variants_count: int
    trade_quality_config: TradeQualityConfig | None = None
    path_diagnostics_config: PathDiagnosticsConfig | None = None
    variants: list[RunVariant]


class RunCompactSummaryReport(BaseModel):
    """Compact ``*.summary.json`` artifact (no trade records or event trace)."""

    model_config = ConfigDict(extra="allow")

    run_id: str
    created_at: str
    report_schema_version: int
    family: str
    symbol: str
    timeframe: str
    data_range: DataRange | None = None
    variants_count: int
    trade_quality_config: TradeQualityConfig | None = None
    path_diagnostics_config: PathDiagnosticsConfig | None = None
    variants: list[RunCompactVariant]
    artifact_kind: Literal["run_summary"] = "run_summary"
    summary_schema_version: int
    source_report_path: str
