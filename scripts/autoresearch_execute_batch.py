#!/usr/bin/env python3
"""Thin standalone adapter to the canonical Research batch lifecycle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from research_service.api.app import create_app
from research_service.application.experiments import BatchExperimentRequest
from research_service.domain.config import ExecutionDraft, StrategyConfigDraft
from research_service.runtime.settings import Settings


def execute_batch(input_path: Path, output_path: Path, settings: Settings | None = None) -> None:
    request = BatchExperimentRequest.model_validate_json(input_path.read_bytes())
    app = create_app(settings)
    container = app.state.container
    services = app.state.services
    try:
        validation = services.config_validation.execute(
            StrategyConfigDraft(
                experiment_id=request.experiment_id,
                strategy_id=request.strategy_id,
                execution=ExecutionDraft(),
                instances=[candidate.strategy for candidate in request.candidates],
            )
        )
        if not validation.ok:
            raise ValueError(
                "candidate validation failed: "
                + json.dumps(validation.model_dump(mode="json"), sort_keys=True)
            )
        result = services.run_batch_experiment.execute(request)
        persisted = services.persist_batch_experiment.execute(request, result)
        payload = {
            "contract_version": "bbb_autoresearch_batch_execution.v1",
            "request_contract_version": "research_batch_experiment.v1",
            "result": result.model_dump(mode="json"),
            "persisted_batch": persisted.model_dump(mode="json"),
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    finally:
        container.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    execute_batch(args.input, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
