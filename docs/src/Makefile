# Documentation Makefile
# Provides convenient commands for linting and formatting documentation

.PHONY: help lint lint-fast format format-check eslint install

# Default target
help:
	@echo "Available targets:"
	@echo "  lint         - Run all linting checks (format, eslint)"
	@echo "  lint-fast    - Same as lint (no build needed for docs)"
	@echo "  format       - Auto-fix code formatting"
	@echo "  format-check - Check code formatting (errors only)"
	@echo "  eslint       - Run ESLint (errors only)"
	@echo "  install      - Install dependencies"

# Main lint target - runs all validation steps
lint: format-check eslint
	@echo ""
	@echo "✅ All lint checks passed!"
	@echo "  ✓ Code formatting"
	@echo "  ✓ ESLint"
	@echo ""
	@echo "💡 Note: Docs has no build step - use 'make lint-fast' for same checks"

# Fast lint (same as regular lint for docs since no build/type-check step)
lint-fast: format-check eslint
	@echo ""
	@echo "✅ Fast lint checks passed!"
	@echo "  ✓ Code formatting"
	@echo "  ✓ ESLint"
	@echo ""
	@echo "💡 Note: Docs linting is already fast (no type-check or build step needed)"

# Auto-fix formatting issues
format:
	@echo "🔧 Auto-fixing code formatting..."
	@npm run format
	@echo "✅ Code formatting complete!"

# Check formatting (fail on errors only)
format-check:
	@echo "🔍 Checking code formatting..."
	@npm run format:check || (echo "❌ Code formatting failed" && exit 1)

# ESLint - errors only
eslint:
	@echo "🔍 Running ESLint..."
	@npm run lint:errors || (echo "❌ ESLint failed" && exit 1)

# Install dependencies
install:
	@echo "📦 Installing dependencies..."
	@npm ci

