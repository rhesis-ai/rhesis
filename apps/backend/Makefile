.PHONY: all format lint lint_diff format_diff type-check test test-lf test-integration test-integration-lf docs docker-up docker-down docker-clean

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

# Unit tests (no docker required)
test:
	uv run pytest -s ../../tests/backend --ignore=../../tests/backend/integration

# Re-run only failed unit tests
test-lf:
	uv run pytest -s ../../tests/backend --lf

# Integration tests (requires docker-compose)
test-integration:
	uv run pytest -s  ../../tests/backend

# Re-run only failed integration tests
test-integration-lf:
	uv run pytest -s ../../tests/backend --lf

# Docker management for integration tests
docker-up:
	docker compose -f ../../tests/backend/integration/docker-compose.yml up -d --wait

docker-down:
	docker compose -f ../../tests/backend/integration/docker-compose.yml down

docker-clean:
	docker compose -f ../../tests/backend/integration/docker-compose.yml down -v

docs:
	cd ../../docs/backend && make clean && make html
