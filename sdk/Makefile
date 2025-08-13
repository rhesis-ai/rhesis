.PHONY: all format lint lint_diff format_diff type-check test docs

all: format_diff lint_diff type-check develop test docs


ALL_FILES := .
DIFF_FILES := $(shell git diff --relative=sdk --name-only --diff-filter=d main | grep -E '\.py$$')


lint:
	uv run --all-groups ruff check $(ALL_FILES)
	uv run --all-groups ruff format $(ALL_FILES) --diff

format:
	uv run --all-groups ruff format $(ALL_FILES)
	uv run --all-groups ruff check --fix $(ALL_FILES)


lint_diff:
	@if [ -n "$(DIFF_FILES)" ]; then \
		uv run --all-groups ruff check $(DIFF_FILES); \
		uv run --all-groups ruff format $(DIFF_FILES) --diff; \
	else \
		echo "No Python file changes detected in git diff with the main branch."; \
	fi


format_diff:
	@if [ -n "$(DIFF_FILES)" ]; then \
		uv run --all-groups ruff format $(DIFF_FILES); \
		uv run --all-groups ruff check --fix $(DIFF_FILES); \
	else \
		echo "No Python file changes detected in git diff with the main branch."; \
	fi

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