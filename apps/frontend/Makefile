# Frontend Makefile
# Mimics the validation script behavior with focus on errors only

.PHONY: help lint lint-fast clean format format-check type-check eslint test build install

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
	@echo "🔍 Running tests..."
	@npm test -- --passWithNoTests --watchAll=false || (echo "❌ Tests failed" && exit 1)

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
