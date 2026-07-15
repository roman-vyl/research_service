.PHONY: test lint typecheck build verify run

test:
	python -m pytest -q

lint:
	python -m ruff check src tests

typecheck:
	python -m mypy src

build:
	python -m build

verify: lint typecheck test build

run:
	uvicorn research_service.api.app:create_app --factory --host 0.0.0.0 --port 8080
