#!/usr/bin/env bash
set -euo pipefail
python scripts/verify_legacy_source.py
python -m ruff check src tests
python -m mypy src
python -m pytest -q
python -m compileall -q src tests
python -m build
