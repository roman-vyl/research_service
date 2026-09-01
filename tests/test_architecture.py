from pathlib import Path
from inspect import Parameter, signature

from research_service.execution.projection_loop import run_projection_execution_loop

ROOT = Path(__file__).parents[1] / "src" / "research_service"


def test_production_code_does_not_import_legacy_bbb_packages() -> None:
    text = "\n".join(path.read_text() for path in ROOT.rglob("*.py"))
    assert "legacy_source" not in text
    assert "from research." not in text
    assert "from research_api." not in text
    assert "import research_api" not in text


def test_domain_and_ports_do_not_import_fastapi_or_httpx() -> None:
    paths = list((ROOT / "domain").rglob("*.py")) + list((ROOT / "ports").rglob("*.py"))
    text = "\n".join(path.read_text() for path in paths)
    assert "fastapi" not in text
    assert "httpx" not in text


def test_canonical_paths_cannot_reach_legacy_quantity_defaults() -> None:
    canonical_paths = (
        ROOT / "application" / "backtests" / "run_backtest.py",
        ROOT / "application" / "backtests" / "materialize_backtest_projection.py",
        ROOT / "application" / "experiments" / "run_batch.py",
    )
    text = "\n".join(path.read_text() for path in canonical_paths)
    assert "run_unified_execution_loop" not in text
    assert "try_open_position" not in text
    assert "execution.entry" not in text

    provider = signature(run_projection_execution_loop).parameters[
        "entry_quantity_provider"
    ]
    assert provider.kind is Parameter.KEYWORD_ONLY
    assert provider.default is Parameter.empty
