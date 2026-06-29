#!/bin/bash
set -e

cd "$(dirname "$0")/.."
echo "Running trace ingestion stress test"
exec uv run python trace_stress/main.py
