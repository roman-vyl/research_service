#!/usr/bin/env bash
set -euo pipefail

export BBB_AUTORESEARCH_LAUNCH_PROFILE="controlled-docker-v1"
export RESEARCH_STRATEGY_ENGINE_URL="http://strategy-engine:8080"
export RESEARCH_MARKET_DATA_URL="http://market-data-service:8080"
export RESEARCH_ARTIFACTS_ROOT="${RESEARCH_ARTIFACTS_ROOT:-/data/runs}"
export RESEARCH_CONFIGS_ROOT="${RESEARCH_CONFIGS_ROOT:-/data/configs}"
export BBB_AUTORESEARCH_RESEARCH_SERVICE_URL="http://research-service:8080"

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python "${repo_root}/scripts/autoresearch_supervisor.py" "$@"
