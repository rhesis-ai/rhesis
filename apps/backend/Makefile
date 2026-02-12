.PHONY: all format lint lint_diff format_diff type-check test test-lf docs docker-up docker-down docker-clean

all: format_diff lint_diff type-check test docs


ALL_FILES := .
DIFF_FILES := $(shell git diff --relative=apps/backend --name-only --diff-filter=d origin/main...HEAD 2>/dev/null | grep -E '\.py' || true)


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

# Tests (starts docker automatically)
test: docker-up
	uv run --extra cpu pytest ../../tests/backend --ignore=../../tests/backend/integration

# Re-run only failed tests
test-lf:
	uv run --extra cpu pytest ../../tests/backend --lf

# Docker management for integration tests
docker-up:
	docker compose -f ../../tests/docker-compose.test.yml --profile backend up -d --wait

docker-down:
	docker compose -f ../../tests/docker-compose.test.yml --profile backend down

docker-clean:
	docker compose -f ../../tests/docker-compose.test.yml --profile backend down -v
