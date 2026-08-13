# Documentation Makefile
# Provides convenient commands for linting and formatting documentation

.PHONY: help lint lint-fast format format-check eslint images titles install

# Default target
help:
	@echo "Available targets:"
	@echo "  lint         - Run all linting checks (format, eslint, images)"
	@echo "  lint-fast    - Same as lint (no build needed for docs)"
	@echo "  format       - Auto-fix code formatting"
	@echo "  format-check - Check code formatting (errors only)"
	@echo "  eslint       - Run ESLint (errors only)"
	@echo "  images       - Check image formats and sizes in public/"
	@echo "  titles       - Check page titles do not repeat the site name"
	@echo "  install      - Install dependencies"

# Main lint target - runs all validation steps
lint: format-check eslint images titles
	@echo ""
	@echo "✅ All lint checks passed!"
	@echo "  ✓ Code formatting"
	@echo "  ✓ ESLint"
	@echo "  ✓ Image formats and sizes"
	@echo "  ✓ Page titles"
	@echo ""
	@echo "💡 Note: Docs has no build step - use 'make lint-fast' for same checks"

# Fast lint (same as regular lint for docs since no build/type-check step)
lint-fast: format-check eslint images titles
	@echo ""
	@echo "✅ Fast lint checks passed!"
	@echo "  ✓ Code formatting"
	@echo "  ✓ ESLint"
	@echo "  ✓ Image formats and sizes"
	@echo "  ✓ Page titles"
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

# Image formats and sizes - keeps screenshot weight out of git history
images:
	@echo "🔍 Checking image formats and sizes..."
	@npm run lint:images || (echo "❌ Image check failed" && exit 1)

# Page titles - the layout already appends " – Rhesis" to every title
titles:
	@echo "🔍 Checking page titles..."
	@npm run lint:titles || (echo "❌ Page title check failed" && exit 1)

# Install dependencies
install:
	@echo "📦 Installing dependencies..."
	@npm ci

