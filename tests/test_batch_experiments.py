from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from research_service.accounting import AccountingPolicy
from research_service.adapters.artifacts.filesystem import FilesystemArtifactStore
from research_service.adapters.http.strategy_engine_client import HttpStrategyEngineClient
from research_service.application.backtests import MaterializeBacktestOutcome
from research_service.application.backtests.artifacts import PersistSingleInstanceBacktest
from research_service.application.experiments import (
    BatchCandidateRequest,
    BatchExperimentRequest,
    PersistBatchExperiment,
    RunBatchExperiment,
)
from research_service.domain.contracts import (
    ContinuityAudit,
    ExplicitRange,
    MarketRange,
    StrategyEvaluationBatchRequest,
    StrategyEvaluationBatchVariant,
    StrategyEvaluationBatchVariantOutcome,
)
from research_service.domain.errors import InvalidRequest, UpstreamServiceError
from research_service.domain.execution import ExecutionPolicy
from research_service.domain.strategy_instance import (
    DeployableStrategyInstance,
    derive_strategy_instance_id,
)
from test_managed_policy_events import ManagedEventsStrategyEngine
from test_single_instance_backtest import (
    FakeMarketData,
    FakeStrategyEngine,
    market_frame,
    strategy_result,
)

_RAW_SPEC = {"anchor": {"period": 200}}


def deployable_instance(marker: str, **overrides: object) -> DeployableStrategyInstance:
    payload: dict[str, object] = {
        "enabled": True,
        "strategy_id": "ema_pullback",
        "ticker": "BTCUSDT.P",
        "base_timeframe": "5m",
        "raw_spec": {**_RAW_SPEC, "_test_marker": marker},
    }
    payload.update(overrides)
    return DeployableStrategyInstance(**payload)  # type: ignore[arg-type]


def candidate(marker: str, **overrides: object) -> BatchCandidateRequest:
    payload: dict[str, object] = {
        "candidate_id": marker,
        "strategy": deployable_instance(marker),
        "execution": ExecutionPolicy(quantity=Decimal("2")),
        "accounting": AccountingPolicy(
            initial_equity=Decimal("1000"),
            entry_fee_rate=Decimal("0.001"),
            exit_fee_rate=Decimal("0.001"),
        ),
        "managed_policy_enabled": False,
    }
    payload.update(overrides)
    return BatchCandidateRequest(**payload)  # type: ignore[arg-type]


def make_request(*candidates: BatchCandidateRequest, **overrides: object) -> BatchExperimentRequest:
    payload: dict[str, object] = {
        "experiment_id": "batch-1",
        "strategy_id": "ema_pullback",
        "range": ExplicitRange(from_ms=0, to_ms=900_000),
        "candidates": candidates or (candidate("a"), candidate("b"), candidate("c")),
        "description": "one shared window batch",
    }
    payload.update(overrides)
    return BatchExperimentRequest(**payload)  # type: ignore[arg-type]


def build_use_case(
    strategy: object, market: FakeMarketData, tmp_path: Path
) -> tuple[RunBatchExperiment, PersistSingleInstanceBacktest]:
    persist_backtest = PersistSingleInstanceBacktest(FilesystemArtifactStore(tmp_path))
    use_case = RunBatchExperiment(
        strategy,  # type: ignore[arg-type]
        market,  # type: ignore[arg-type]
        MaterializeBacktestOutcome(strategy),  # type: ignore[arg-type]
        persist_backtest,
    )
    return use_case, persist_backtest


def test_batch_runs_all_candidates_and_shares_one_evaluation(tmp_path: Path) -> None:
    strategy = FakeStrategyEngine(strategy_result())
    market = FakeMarketData(market_frame())
    use_case, _ = build_use_case(strategy, market, tmp_path)

    result = use_case.execute(make_request())

    assert result.status == "completed"
    assert result.completed_count == 3
    assert result.failed_count == 0
    assert [item.candidate_id for item in result.candidates] == ["a", "b", "c"]
    assert all(item.status == "completed" for item in result.candidates)
    assert all(item.run_id for item in result.candidates)
    assert len({item.run_id for item in result.candidates}) == 3
    assert len({item.instance_id for item in result.candidates}) == 3


# --- Shared acquisition: the main acceptance test ---------------------------


def test_n_candidates_share_one_window_resolution_one_frame_read_one_batch_call(
    tmp_path: Path,
) -> None:
    strategy = FakeStrategyEngine(strategy_result())
    market = FakeMarketData(market_frame())
    use_case, _ = build_use_case(strategy, market, tmp_path)

    use_case.execute(make_request(candidate("a"), candidate("b"), candidate("c"), candidate("d")))

    assert market.audit_calls == 1
    assert market.bounds_calls == 0  # explicit_range: no MDS bounds lookup
    assert len(market.requests) == 1  # read_historical_range called once
    assert len(strategy.batch_requests) == 1  # evaluate_range_batch called once
    assert len(strategy.batch_requests[0].variants) == 4
    assert strategy.range_requests == []  # evaluate_range (single) never called


def test_full_available_shared_window_uses_bounds_once(tmp_path: Path) -> None:
    strategy = FakeStrategyEngine(strategy_result())
    market = FakeMarketData(market_frame())
    use_case, _ = build_use_case(strategy, market, tmp_path)

    use_case.execute(
        make_request(candidate("a"), candidate("b"), range_policy="full_available", range=None)
    )

    assert market.bounds_calls == 1
    assert market.audit_calls == 1
    assert len(market.requests) == 1
    assert len(strategy.batch_requests) == 1


# --- Engine wire shape --------------------------------------------------------


def test_engine_batch_wire_uses_candidate_id_as_variant_id_and_canonical_strategy(
    tmp_path: Path,
) -> None:
    strategy = FakeStrategyEngine(strategy_result())
    market = FakeMarketData(market_frame())
    use_case, _ = build_use_case(strategy, market, tmp_path)

    use_case.execute(make_request())

    sent = strategy.batch_requests[0]
    assert sent.market == market_frame().market
    assert sent.expected_market_data_hash == "market-hash"
    assert [v.variant_id for v in sent.variants] == ["a", "b", "c"]
    for v in sent.variants:
        assert v.strategy_id == "ema_pullback"
        assert v.strategy_spec["_test_marker"] == v.variant_id
        assert v.instance_id


def test_http_client_sends_no_enabled_instance_id_or_run_id_on_batch_wire() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "variants": [
                    {
                        "variant_id": "a",
                        "result": {
                            "contract_version": "strategy_evaluation.v1",
                            "strategy_id": "ema_pullback",
                            "config_hash": "cfg",
                            "market": {
                                "ticker": "BTCUSDT.P",
                                "base_timeframe": "5m",
                                "from_ms": 0,
                                "to_ms": 300_000,
                                "bar_count": 1,
                                "market_data_hash": "md",
                            },
                            "features": {"time_ms": [0]},
                            "contexts": {},
                            "entries": {"long": [False]},
                            "exit_policy": {
                                "signal_exit": {"long": [False], "short": [False]},
                                "stop_loss_ratio": {"long": [None], "short": [None]},
                                "take_profit_ratio": {"long": [None], "short": [None]},
                                "stop_ready": {"long": [False], "short": [False]},
                            },
                            "component_evidence": {},
                            "validity": {},
                            "state_artifact": None,
                            "warnings": [],
                        },
                        "error": None,
                    }
                ]
            },
        )

    client = HttpStrategyEngineClient("http://strategy")
    client._client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://strategy")

    outcomes = client.evaluate_range_batch(
        StrategyEvaluationBatchRequest(
            market=MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=300_000),
            variants=(
                StrategyEvaluationBatchVariant(
                    variant_id="a",
                    instance_id="ema_pullback:should-not-appear-on-wire",
                    strategy_id="ema_pullback",
                    strategy_spec={"anchor": {"period": 200}},
                ),
            ),
            expected_market_data_hash="shared-hash",
        )
    )

    body = seen["body"]
    assert isinstance(body, dict)
    sent_variant = body["variants"][0]
    assert set(sent_variant) == {"variant_id", "strategy"}
    assert set(sent_variant["strategy"]) == {"strategy_id", "raw_spec"}
    assert "enabled" not in sent_variant
    assert "instance_id" not in sent_variant
    assert "run_id" not in body
    assert body["expected_market_data_hash"] == "shared-hash"
    assert outcomes[0].result is not None
    assert outcomes[0].result.instance_id == "ema_pullback:should-not-appear-on-wire"


# --- Response correlation -----------------------------------------------------


def test_shuffled_engine_response_order_still_maps_correctly(tmp_path: Path) -> None:
    strategy = FakeStrategyEngine(strategy_result(), shuffle_response=True)
    market = FakeMarketData(market_frame())
    use_case, _ = build_use_case(strategy, market, tmp_path)

    result = use_case.execute(make_request())

    assert [item.candidate_id for item in result.candidates] == ["a", "b", "c"]
    assert all(item.status == "completed" for item in result.candidates)
    for item in result.candidates:
        expected = derive_strategy_instance_id(
            strategy_id="ema_pullback",
            ticker="BTCUSDT.P",
            base_timeframe="5m",
            raw_spec={**_RAW_SPEC, "_test_marker": item.candidate_id},
        )
        assert item.instance_id == expected


def test_http_client_rejects_unknown_variant_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "variants": [
                    {
                        "variant_id": "ghost",
                        "result": None,
                        "error": {"error": "x", "message": "x", "details": {}},
                    }
                ]
            },
        )

    client = HttpStrategyEngineClient("http://strategy")
    client._client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://strategy")

    with pytest.raises(UpstreamServiceError) as exc_info:
        client.evaluate_range_batch(
            StrategyEvaluationBatchRequest(
                market=MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=300_000),
                variants=(
                    StrategyEvaluationBatchVariant(
                        variant_id="a", instance_id="i", strategy_id="ema_pullback", strategy_spec={}
                    ),
                ),
            )
        )
    assert "unrequested variant_id" in exc_info.value.message


def test_http_client_rejects_duplicate_variant_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        entry = {
            "variant_id": "a",
            "result": None,
            "error": {"error": "x", "message": "x", "details": {}},
        }
        return httpx.Response(200, json={"variants": [entry, entry]})

    client = HttpStrategyEngineClient("http://strategy")
    client._client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://strategy")

    with pytest.raises(UpstreamServiceError) as exc_info:
        client.evaluate_range_batch(
            StrategyEvaluationBatchRequest(
                market=MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=300_000),
                variants=(
                    StrategyEvaluationBatchVariant(
                        variant_id="a", instance_id="i", strategy_id="ema_pullback", strategy_spec={}
                    ),
                ),
            )
        )
    assert "duplicate variant_id" in exc_info.value.message


def test_http_client_rejects_missing_candidate_outcome() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"variants": []})

    client = HttpStrategyEngineClient("http://strategy")
    client._client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://strategy")

    with pytest.raises(UpstreamServiceError) as exc_info:
        client.evaluate_range_batch(
            StrategyEvaluationBatchRequest(
                market=MarketRange(ticker="BTCUSDT.P", timeframe="5m", from_ms=0, to_ms=300_000),
                variants=(
                    StrategyEvaluationBatchVariant(
                        variant_id="a", instance_id="i", strategy_id="ema_pullback", strategy_spec={}
                    ),
                ),
            )
        )
    assert "missing candidate outcome" in exc_info.value.message


# --- Instance identity ---------------------------------------------------------


def test_each_successful_candidate_gets_correct_research_derived_instance_id(
    tmp_path: Path,
) -> None:
    strategy = FakeStrategyEngine(strategy_result())
    market = FakeMarketData(market_frame())
    use_case, _ = build_use_case(strategy, market, tmp_path)

    result = use_case.execute(make_request())

    for item in result.candidates:
        expected = derive_strategy_instance_id(
            strategy_id="ema_pullback",
            ticker="BTCUSDT.P",
            base_timeframe="5m",
            raw_spec={**_RAW_SPEC, "_test_marker": item.candidate_id},
        )
        assert item.instance_id == expected


def test_different_raw_spec_yields_different_instance_id(tmp_path: Path) -> None:
    strategy = FakeStrategyEngine(strategy_result())
    market = FakeMarketData(market_frame())
    use_case, _ = build_use_case(strategy, market, tmp_path)

    result = use_case.execute(make_request(candidate("a"), candidate("b")))

    assert result.candidates[0].instance_id != result.candidates[1].instance_id


# --- Failure semantics ----------------------------------------------------------


class DiscontinuousMarketData(FakeMarketData):
    def audit_range(self, market: MarketRange) -> ContinuityAudit:
        self.audit_calls += 1
        audit = super().audit_range(market)
        return audit.model_copy(update={"is_continuous": False, "gaps": ()})


def test_shared_window_failure_makes_zero_batch_calls_and_persists_nothing(
    tmp_path: Path,
) -> None:
    strategy = FakeStrategyEngine(strategy_result())
    market = DiscontinuousMarketData(market_frame())
    use_case, _ = build_use_case(strategy, market, tmp_path)

    with pytest.raises(InvalidRequest, match="not continuous"):
        use_case.execute(make_request())

    assert strategy.batch_requests == []
    assert market.requests == []


class FailingBatchStrategyEngine(FakeStrategyEngine):
    def evaluate_range_batch(self, request: object) -> object:  # type: ignore[override]
        raise UpstreamServiceError(service="strategy_engine", status_code=503, message="down")


def test_engine_batch_http_failure_persists_nothing(tmp_path: Path) -> None:
    strategy = FailingBatchStrategyEngine(strategy_result())
    market = FakeMarketData(market_frame())
    use_case, _ = build_use_case(strategy, market, tmp_path)

    with pytest.raises(UpstreamServiceError):
        use_case.execute(make_request())

    assert market.requests == []  # shared frame read never reached


def test_one_per_variant_engine_error_isolates_that_candidate(tmp_path: Path) -> None:
    strategy = FakeStrategyEngine(strategy_result(), failing_variant_ids=frozenset({"b"}))
    market = FakeMarketData(market_frame())
    use_case, _ = build_use_case(strategy, market, tmp_path)

    result = use_case.execute(make_request())

    assert result.status == "completed_with_failures"
    assert result.completed_count == 2
    assert result.failed_count == 1
    failed = result.candidates[1]
    assert failed.candidate_id == "b"
    assert failed.status == "failed"
    assert failed.run_id is None
    assert failed.instance_id
    assert failed.error_type == "StrategyEngineVariantError"
    assert result.candidates[0].status == "completed"
    assert result.candidates[2].status == "completed"


class MismatchOnBStrategyEngine(FakeStrategyEngine):
    def evaluate_range_batch(
        self, request: StrategyEvaluationBatchRequest
    ) -> tuple[StrategyEvaluationBatchVariantOutcome, ...]:
        self.batch_requests.append(request)
        outcomes = []
        for variant in request.variants:
            if variant.variant_id == "b":
                bad = self.result.model_copy(
                    update={
                        "instance_id": variant.instance_id,
                        "market": MarketRange(
                            ticker="ETHUSDT.P", timeframe="5m", from_ms=0, to_ms=900_000
                        ),
                    }
                )
                outcomes.append(
                    StrategyEvaluationBatchVariantOutcome(variant_id=variant.variant_id, result=bad)
                )
            else:
                outcomes.append(
                    StrategyEvaluationBatchVariantOutcome(
                        variant_id=variant.variant_id,
                        result=self.result.model_copy(update={"instance_id": variant.instance_id}),
                    )
                )
        return tuple(outcomes)


def test_one_materialize_failure_isolates_that_candidate_siblings_persist(
    tmp_path: Path,
) -> None:
    strategy = MismatchOnBStrategyEngine(strategy_result())
    market = FakeMarketData(market_frame())
    use_case, _ = build_use_case(strategy, market, tmp_path)

    result = use_case.execute(make_request())

    assert result.completed_count == 2
    assert result.failed_count == 1
    failed = next(item for item in result.candidates if item.candidate_id == "b")
    assert failed.status == "failed"
    assert failed.run_id is None
    assert "market" in failed.error_message.lower() or "differ" in failed.error_message.lower()

    completed = [item for item in result.candidates if item.status == "completed"]
    assert len(completed) == 2
    for item in completed:
        assert item.run_id is not None
        assert (tmp_path / item.run_id / "result.json").is_file()


# --- Persistence / managed events ------------------------------------------------


def test_successful_candidates_create_independent_canonical_run_artifacts(
    tmp_path: Path,
) -> None:
    strategy = FakeStrategyEngine(strategy_result())
    market = FakeMarketData(market_frame())
    use_case, _ = build_use_case(strategy, market, tmp_path)

    result = use_case.execute(make_request())

    run_ids = [item.run_id for item in result.candidates]
    assert len(set(run_ids)) == 3
    for run_id in run_ids:
        assert run_id is not None
        assert (tmp_path / run_id / "result.json").is_file()
        assert (tmp_path / run_id / "request.json").is_file()
        assert (tmp_path / run_id / "manifest.json").is_file()


def test_batch_artifacts_are_published_atomically(tmp_path: Path) -> None:
    strategy = FakeStrategyEngine(strategy_result())
    market = FakeMarketData(market_frame())
    use_case, _ = build_use_case(strategy, market, tmp_path)
    request = make_request()

    result = use_case.execute(request)
    persisted = PersistBatchExperiment(FilesystemArtifactStore(tmp_path)).execute(request, result)

    destination = tmp_path / "batches" / "batch-1"
    assert persisted.artifact_path == str(destination)
    assert (destination / "request.json").is_file()
    assert (destination / "summary.json").is_file()
    assert (destination / "manifest.json").is_file()
    assert len(persisted.summary_sha256) == 64


def test_batch_candidate_with_managed_policy_persists_real_events(tmp_path: Path) -> None:
    """Regression: a managed candidate, run through the new shared-evaluation
    batch path, must persist the real managed-policy events captured by
    MaterializeBacktestOutcome's one authoritative outcome."""

    strategy = ManagedEventsStrategyEngine(strategy_result())
    market = FakeMarketData(market_frame())
    use_case, _ = build_use_case(strategy, market, tmp_path)
    request = make_request(candidate("managed-a", managed_policy_enabled=True))

    result = use_case.execute(request)

    assert result.status == "completed"
    assert result.candidates[0].status == "completed"
    run_id = result.candidates[0].run_id
    assert run_id

    events_path = tmp_path / run_id / "managed_policy_events.json"
    trace = json.loads(events_path.read_text(encoding="utf-8"))
    assert trace["run_id"] == run_id
    assert len(trace["events"]) == 2
    assert {event["event_type"] for event in trace["events"]} == {
        "phase_changed",
        "active_stop_updated",
    }


# --- Contract-level rejection -----------------------------------------------------


def test_batch_contract_rejects_duplicate_candidate_ids() -> None:
    same = candidate("same")
    with pytest.raises(ValueError, match="candidate_id values must be unique"):
        make_request(same, same)


def test_full_available_dummy_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="full_available must not include a range"):
        make_request(range_policy="full_available", range=ExplicitRange(from_ms=0, to_ms=1))


def test_explicit_range_without_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="explicit_range requires"):
        make_request(range=None)


def test_mismatched_candidate_strategy_id_is_rejected() -> None:
    bad = candidate("bad", strategy=deployable_instance("bad", strategy_id="other_strategy"))
    with pytest.raises(ValueError, match="strategy_id must match"):
        make_request(candidate("a"), bad)


def test_mismatched_candidate_ticker_is_rejected() -> None:
    bad = candidate("bad", strategy=deployable_instance("bad", ticker="ETHUSDT.P"))
    with pytest.raises(ValueError, match="same strategy.ticker"):
        make_request(candidate("a"), bad)


def test_mismatched_candidate_base_timeframe_is_rejected() -> None:
    bad = candidate("bad", strategy=deployable_instance("bad", base_timeframe="1h"))
    with pytest.raises(ValueError, match="same strategy.base_timeframe"):
        make_request(candidate("a"), bad)


def test_legacy_candidate_backtest_shape_is_rejected() -> None:
    with pytest.raises(ValidationError):
        BatchCandidateRequest(  # type: ignore[call-arg]
            candidate_id="legacy",
            backtest={"strategy": {}},  # old shape: nested standalone backtest request
        )
