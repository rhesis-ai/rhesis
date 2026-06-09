# Frontend Makefile
# Mimics the validation script behavior with focus on errors only

.PHONY: help lint lint-fast clean format format-check type-check eslint test test-coverage build install docker-up docker-down docker-clean test-e2e test-e2e-ci

# Default target
help:
	@echo "Available targets:"
	@echo "  lint         - Run all linting checks (format, type-check, eslint, build)"
	@echo "  lint-fast    - Run fast linting checks (skip build validation)"
	@echo "  clean        - Remove build artifacts"
	@echo "  format       - Auto-fix code formatting"
	@echo "  format-check - Check code formatting (errors only)"
	@echo "  type-check   - Run TypeScript type checking"
	@echo "  eslint       - Run ESLint (errors only)"
	@echo "  test         - Run tests"
	@echo "  test-coverage - Run tests with coverage (matches CI)"
	@echo "  build        - Build the application"
	@echo "  install      - Install dependencies"

# Main lint target - runs all validation steps (full by default)
lint: clean format-check type-check eslint build
	@echo ""
	@echo "✅ All lint checks passed!"
	@echo "  ✓ Code formatting"
	@echo "  ✓ TypeScript validation"
	@echo "  ✓ ESLint (errors only)"
	@echo "  ✓ Build process"
	@echo ""
	@echo "💡 Tip: Use 'make lint-fast' to skip build validation for faster checks"

# Fast lint without build step
lint-fast: format-check type-check eslint
	@echo ""
	@echo "✅ Fast lint checks passed!"
	@echo "  ✓ Code formatting"
	@echo "  ✓ TypeScript validation"
	@echo "  ✓ ESLint (errors only)"
	@echo "  ⚠ Build validation skipped (use 'make lint' for full validation)"
	@echo ""

# Clean build artifacts
clean:
	@echo "🗑️ Cleaning .next folder..."
	@npm run clean

# Auto-fix formatting issues
format:
	@echo "🔧 Auto-fixing code formatting..."
	@npm run format

# Check formatting (fail on errors only)
format-check:
	@echo "🔍 Checking code formatting..."
	@npm run format:check || (echo "❌ Code formatting failed" && exit 1)

# TypeScript type checking
type-check:
	@echo "🔍 Checking for TypeScript errors..."
	@npm run type-check || (echo "❌ TypeScript validation failed" && exit 1)

# ESLint - errors only, ignore warnings
eslint:
	@echo "🔍 Running ESLint (errors only)..."
	@if npm run lint 2>&1 | grep -q "Error:"; then \
		echo "❌ ESLint found errors (not just warnings)"; \
		exit 1; \
	else \
		echo "✅ Only ESLint warnings found (no errors)"; \
	fi

# Run tests
test:
	npm test -- --passWithNoTests --ci --watchAll=false

# Run tests with coverage (matches CI)
test-coverage:
	npm run test:ci

# Build the application
build:
	@echo "🔍 Testing build process..."
	@npx next build || (echo "❌ Build process failed" && exit 1)
	@echo "🗑️ Cleaning up build artifacts..."
	@npm run clean

# Install dependencies
install:
	@echo "📦 Installing dependencies..."
	@npm ci --legacy-peer-deps

# Docker management for E2E tests
BACKEND_E2E_PORT := 14003

docker-up:
	docker compose -f ../../tests/docker-compose.frontend.yml up -d --build --wait

docker-build:
	docker compose -f ../../tests/docker-compose.frontend.yml build frontend-test-backend

docker-up-no-build:
	docker compose -f ../../tests/docker-compose.frontend.yml up -d --wait

docker-down:
	docker compose -f ../../tests/docker-compose.frontend.yml down

docker-clean:
	docker compose -f ../../tests/docker-compose.frontend.yml down -v

# Shared env for Playwright runs against the Docker Quick Start backend
E2E_DOCKER_ENV = API_BASE_URL=http://localhost:$(BACKEND_E2E_PORT) \
	BACKEND_URL=http://localhost:$(BACKEND_E2E_PORT) \
	NEXTAUTH_SECRET=test-secret-for-e2e-tests-only \
	NEXTAUTH_URL=http://localhost:3000

# Live-backend Playwright args — @mocked specs run only via test-e2e-local
E2E_DOCKER_GREP = --grep "@sanity|@crud" --grep-invert "@mocked"

# E2E tests (starts docker automatically)
# Runs @sanity smoke tests on both Chromium and Firefox, plus @crud interaction tests on Chromium only
test-e2e: docker-up
	$(E2E_DOCKER_ENV) npx playwright test $(E2E_DOCKER_GREP)

# Playwright only — assumes Docker stack is already up (CI shards after prepare-docker)
test-e2e-run-ci:
	$(E2E_DOCKER_ENV) npx playwright test $(E2E_DOCKER_GREP) --project=chromium

# CI E2E — Chromium only (Firefox browser install is skipped in GitHub Actions)
test-e2e-ci: docker-up
	$(E2E_DOCKER_ENV) npx playwright test $(E2E_DOCKER_GREP) --project=chromium

# CI E2E — reuse a pre-built backend image (see frontend-e2e-test.yml prepare-docker job)
test-e2e-ci-no-build: docker-up-no-build
	$(E2E_DOCKER_ENV) npx playwright test $(E2E_DOCKER_GREP) --project=chromium

# Run only @sanity smoke tests (faster, cross-browser)
test-e2e-smoke: docker-up
	$(E2E_DOCKER_ENV) npx playwright test --grep "@sanity" --grep-invert "@mocked"

# Local E2E without Docker — mocks API in-browser; auth seeded locally.
test-e2e-local:
	E2E_NO_DOCKER=1 \
	FRONTEND_ENV=development \
	NEXTAUTH_SECRET=test-secret-for-e2e-tests-only \
	NEXTAUTH_URL=http://localhost:3100 \
	npx playwright test --grep "@mocked" --project=mocked
