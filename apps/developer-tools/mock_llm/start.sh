#!/bin/bash
set -e

cd "$(dirname "$0")/.."
echo "Starting mock LLM server on port 18080"
exec uv run python mock_llm/main.py
