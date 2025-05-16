#!/bin/bash

# Clean before building to ensure a fresh build
echo "🗑️ Cleaning .next folder..."
npm run clean

echo "🔍 Checking for TypeScript errors..."
npm run type-check
TS_EXIT_CODE=$?

echo "🔍 Running linter..."
npm run lint
LINT_EXIT_CODE=$?

echo "🔍 Testing build process..."

# Use --no-lint to skip linting (since we already did it)
echo "Running build with --no-lint..."
npx next build --no-lint
BUILD_EXIT_CODE=$?

# Clean up the build artifacts after validation
echo "Cleaning up build artifacts..."
npm run clean

if [ $TS_EXIT_CODE -eq 0 ] && [ $LINT_EXIT_CODE -eq 0 ] && [ $BUILD_EXIT_CODE -eq 0 ]; then
    echo "✅ All checks passed!"
    exit 0
else
    echo "❌ Validation failed. Please fix the errors before building the container."
    exit 1
fi 