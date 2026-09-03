#!/usr/bin/env bash
set -euo pipefail

export BBB_AUTORESEARCH_LAUNCH_PROFILE="controlled-host-v1"
export BBB_AUTORESEARCH_RESEARCH_SERVICE_URL="http://127.0.0.1:8000"
export RESEARCH_STRATEGY_ENGINE_URL="http://127.0.0.1:8090"
export RESEARCH_MARKET_DATA_URL="http://127.0.0.1:8080"
export RESEARCH_ARTIFACTS_ROOT="${HOME}/bbb_data/autoresearch"
export RESEARCH_CONFIGS_ROOT="${HOME}/bbb_data/autoresearch/configs"

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
venv_python="${repo_root}/.venv/bin/python"

if [[ ! -x "${venv_python}" ]]; then
  echo "repo-local virtualenv is missing or not ready: ${venv_python} is not an executable file (run the project's venv setup first)" >&2
  exit 2
fi

if [[ $# -eq 0 ]]; then
  echo "usage: $0 init|run [arguments...]" >&2
  exit 2
fi

action="$1"
shift
case "${action}" in
  init)
    entrypoint="${repo_root}/scripts/autoresearch_init.py"
    ;;
  run)
    entrypoint="${repo_root}/scripts/autoresearch_supervisor.py"
    ;;
  *)
    echo "usage: $0 init|run [arguments...]" >&2
    exit 2
    ;;
esac

exec "${venv_python}" "${entrypoint}" "$@"
