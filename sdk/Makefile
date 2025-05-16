.PHONY: all format lint type-check test docs

all: format lint type-check develop test docs

format:

	ruff format src

lint:
	ruff check --fix src

type-check:
	PYTHONPATH=src mypy --install-types --non-interactive
	PYTHONPATH=src mypy --package rhesis.sdk

develop:
	uv sync --dev
	uv pip install -e .

test:
	pytest

docs:
	cd ../docs/sdk && make clean && make html