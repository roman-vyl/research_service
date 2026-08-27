"""Canonical strategy-instance identity, shared by Composer, Research Service,
and Strategy Runtime (`canonical-strategy-instance-v1`).

Identity subset: `strategy_id` + `ticker` + `base_timeframe` + `raw_spec`.
`instance_id` is never stored or accepted as input — it is always derived
from the identity subset via `derive_strategy_instance_id`, mirroring
Strategy Runtime's own derivation exactly so both systems compute the
identical value for the identical instance.

`enabled` is deployment/activation metadata layered on top of the identity
subset in `DeployableStrategyInstance` — it plays no role in the derivation
and never reaches Research backtest evaluation, which only ever needs the
identity subset.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

from research_service.domain.contracts import timeframe_ms

_TICKER_PATTERN = r"^[A-Z0-9]+\.P$"


def _validate_base_timeframe(value: str) -> str:
    timeframe_ms(value)  # raises ValueError for an unsupported timeframe
    return value


class StrategyInstanceIdentity(BaseModel):
    """The four fields that determine a strategy instance's identity.

    No other field belongs here — `enabled`, `instance_id`, `family`,
    `variant`, and `strategy_version` are all rejected by `extra="forbid"`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy_id: str = Field(min_length=1)
    ticker: str = Field(pattern=_TICKER_PATTERN)
    base_timeframe: str
    raw_spec: dict[str, Any]

    @field_validator("base_timeframe")
    @classmethod
    def validate_base_timeframe(cls, value: str) -> str:
        return _validate_base_timeframe(value)


class DeployableStrategyInstance(BaseModel):
    """Flat deployable document: identity subset + sibling `enabled`.

    Structurally identical to Strategy Runtime's deployment-file shape —
    no nested identity/deployment structure. Composer stores and edits
    this; Research config persistence stores collections of it; a future
    Runtime-deployment boundary (not part of this change) consumes it
    unchanged.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool
    strategy_id: str = Field(min_length=1)
    ticker: str = Field(pattern=_TICKER_PATTERN)
    base_timeframe: str
    raw_spec: dict[str, Any]

    @field_validator("base_timeframe")
    @classmethod
    def validate_base_timeframe(cls, value: str) -> str:
        return _validate_base_timeframe(value)

    def identity(self) -> StrategyInstanceIdentity:
        """Project the identity subset out of this deployable document.

        `enabled` is deliberately dropped here — this is the one place
        that turns "the document Composer edits" into "the input a
        backtest needs," and it must never carry `enabled` forward.
        """
        return StrategyInstanceIdentity(
            strategy_id=self.strategy_id,
            ticker=self.ticker,
            base_timeframe=self.base_timeframe,
            raw_spec=self.raw_spec,
        )


def derive_strategy_instance_id(
    *,
    strategy_id: str,
    ticker: str,
    base_timeframe: str,
    raw_spec: Mapping[str, Any],
) -> str:
    """Deterministic identity, mirroring Strategy Runtime's
    `derive_strategy_instance_id` exactly (same field set, same canonical
    JSON encoding, same digest length) so both systems compute the
    identical `instance_id` for the identical instance. `enabled` MUST NOT
    be an input to this function.
    """

    identity_payload = {
        "strategy_id": strategy_id,
        "ticker": ticker,
        "base_timeframe": base_timeframe,
        "raw_spec": raw_spec,
    }
    canonical_payload = json.dumps(
        identity_payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(canonical_payload).hexdigest()[:24]
    return f"{strategy_id}:{digest}"
