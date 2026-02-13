.PHONY: all format lint lint_diff format_diff type-check test test-integration test-coverage docker-up docker-down docker-clean

all: format_diff lint_diff type-check test


ALL_FILES := .
DIFF_FILES := $(shell git diff --relative=sdk --name-only --diff-filter=d origin/main...HEAD 2>/dev/null | grep -E '\.py' || true)


lint:
	uvx ruff check $(ALL_FILES)
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
		uvx ruff check --fix $(DIFF_FILES); \
	else \
		echo "No Python file changes detected in git diff with the main branch."; \
	fi

test:
	uv run pytest -s ../tests/sdk --ignore=../tests/sdk/integration

# Docker management for integration tests
docker-up:
	docker compose -f ../tests/docker-compose.test.yml --profile sdk up -d --build --wait

docker-down:
	docker compose -f ../tests/docker-compose.test.yml --profile sdk down

docker-clean:
	docker compose -f ../tests/docker-compose.test.yml --profile sdk down -v

test-integration: docker-up
	uv run pytest -s ../tests/sdk

test-coverage:
	uv run pytest ../tests/sdk --cov=src/rhesis --cov-report=term-missing --cov-report=html
