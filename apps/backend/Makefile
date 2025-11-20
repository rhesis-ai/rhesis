.PHONY: all format lint lint_diff format_diff type-check test docs

all: format_diff lint_diff type-check test docs


ALL_FILES := .
DIFF_FILES := $(shell git diff --relative=apps/backend --name-only --diff-filter=d main... | grep -E '\.py')


lint:
	# uvx ruff check $(ALL_FILES)
	uvx ruff format $(ALL_FILES) --check

format:
	uvx ruff format $(ALL_FILES)
	uvx ruff check --fix $(ALL_FILES)


lint_diff:
	@if [ -n "$(DIFF_FILES)" ]; then \
		uvx ruff check $(DIFF_FILES); \
		uvx ruff format $(DIFF_FILES) --check; \
	else \
		echo "No Python file changes detected in git diff with the main branch."; \
	fi


format_diff:
	@if [ -n "$(DIFF_FILES)" ]; then \
		uvx ruff format $(DIFF_FILES); \
	else \
		echo "No Python file changes detected in git diff with the main branch."; \
	fi

type-check:
	PYTHONPATH=src mypy --install-types --non-interactive
	PYTHONPATH=src mypy --package rhesis.backend

test:
	pytest

docs:
	cd ../../docs/backend && make clean && make html
