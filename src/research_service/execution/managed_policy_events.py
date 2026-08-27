"""Managed-policy event trace: canonical Research capture of Engine managed-replay evidence.

Strategy Engine's managed replay (`ManagedReplayResult.events`, see
`research_service.domain.contracts`) is evidence describing *why* the managed
exit policy behaved as it did for one position — phase transitions and
active-stop/active-take/runtime-exit updates. `execution/loop.py` consumes
this evidence to decide exits but has no reason to retain it once a position
closes. This module captures that evidence, tagged with the deterministic
Research-owned `position_id`/`side` identity, so it survives past the loop
for persistence and projection — without folding it into execution/accounting
results.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from research_service.domain.contracts import ManagedReplayResult
from research_service.domain.execution import ExecutionSide

ManagedPolicyEventType = Literal[
    "phase_changed",
    "active_stop_updated",
    "active_take_updated",
    "runtime_exit_triggered",
]


class ManagedPolicyEvent(BaseModel):
    """One Engine-sourced managed-policy event, attributed to a Research position."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Deterministic correlation key: equals TradeRecord.position_id (NOT
    # TradeRecord.trade_id, which is a derived "trade:{position_id}:{ordinal}"
    # string) — see execution/managed_policy_events.capture_managed_policy_events.
    position_id: str = Field(min_length=1)
    side: ExecutionSide
    time_ms: int = Field(ge=0)
    bar_index: int = Field(ge=0)
    event_type: ManagedPolicyEventType
    rule_id: str | None = None
    component_id: str | None = None
    from_phase: str | None = None
    to_phase: str | None = None
    price: Decimal | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ManagedPolicyEventTrace(BaseModel):
    """Run-scoped bundle of managed-policy events, one file per immutable run bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["research_managed_policy_events.v1"] = (
        "research_managed_policy_events.v1"
    )
    run_id: str = Field(min_length=1)
    events: tuple[ManagedPolicyEvent, ...] = ()


def capture_managed_policy_events(
    replay: ManagedReplayResult,
    *,
    position_id: str,
    side: ExecutionSide,
) -> tuple[ManagedPolicyEvent, ...]:
    """Convert one Engine managed-replay response into typed, attributed records.

    `position_id`/`side` are passed by the caller (Research already knows
    them — they were sent as `ManagedReplayRequest.trade_id`/`side`) rather
    than read back off the Engine response, matching `position.position_id`
    as sent, not re-derived or guessed from wire content.
    """

    events: list[ManagedPolicyEvent] = []
    for item in replay.events:
        # `item` is a raw `dict[str, object]` from the Engine's JSON response
        # (see ManagedReplayResult.events); cast satisfies the type checker
        # the same way `strategy_engine_client._int`/`_object` do — pydantic
        # validation on ManagedPolicyEvent below still fails closed on a
        # malformed upstream value.
        raw = cast("dict[str, Any]", item)
        events.append(
            ManagedPolicyEvent(
                position_id=position_id,
                side=side,
                time_ms=int(raw["time_ms"]),
                bar_index=int(raw["bar_index"]),
                event_type=raw["event_type"],
                rule_id=raw.get("rule_id"),
                component_id=raw.get("component_id"),
                from_phase=raw.get("from_phase"),
                to_phase=raw.get("to_phase"),
                price=raw.get("price"),
                metadata=dict(raw.get("metadata") or {}),
            )
        )
    return tuple(events)
