.PHONY: all format lint type-check develop test docs

all: format lint type-check develop test docs

format:
	ruff format src

lint:
	ruff check --fix src

type-check:
	PYTHONPATH=src mypy --install-types --non-interactive
	PYTHONPATH=src mypy --package rhesis.backend

develop:
	uv sync --extra dev
	uv pip install -e .

test:
	pytest

docs:
	cd ../../docs/backend && make clean && make html 