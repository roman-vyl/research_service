from pathlib import Path

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
