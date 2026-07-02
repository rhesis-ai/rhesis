#!/bin/bash
set -e

cd "$(dirname "$0")/.."
echo "Starting mock chatbot server on port 18090"
exec uv run python mock_chatbot/main.py
