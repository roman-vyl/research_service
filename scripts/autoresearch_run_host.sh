#!/usr/bin/env bash
set -euo pipefail

: "${RESEARCH_ARTIFACTS_ROOT:?set RESEARCH_ARTIFACTS_ROOT to an absolute host path}"
: "${RESEARCH_CONFIGS_ROOT:?set RESEARCH_CONFIGS_ROOT to an absolute host path}"
: "${BBB_AUTORESEARCH_RESEARCH_SERVICE_URL:?set BBB_AUTORESEARCH_RESEARCH_SERVICE_URL to the Research Services own base URL on this host; no canonical HOST-profile port is documented, and 8080 collides with Market Data Service}"

if [[ "${RESEARCH_ARTIFACTS_ROOT}" != /* ]]; then
  echo "RESEARCH_ARTIFACTS_ROOT must be an absolute host path" >&2
  exit 2
fi
if [[ "${RESEARCH_CONFIGS_ROOT}" != /* ]]; then
  echo "RESEARCH_CONFIGS_ROOT must be an absolute host path" >&2
  exit 2
fi

export RESEARCH_STRATEGY_ENGINE_URL="http://127.0.0.1:8090"
export RESEARCH_MARKET_DATA_URL="http://127.0.0.1:8080"

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python "${repo_root}/scripts/autoresearch_supervisor.py" "$@"
