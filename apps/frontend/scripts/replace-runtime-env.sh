#!/bin/sh
# Replace build-time placeholders in the Next.js bundle with runtime values
# before starting the standalone server.
#
# Placeholders baked into the bundle at build time:
#   __NEXT_PUBLIC_API_BASE_URL__  -> API_BASE_URL | BACKEND_URL | localhost:8080
#   __NEXT_PUBLIC_QUICK_START__   -> QUICK_START | false
#
# This allows a single Docker image to be used for all deployment modes.

set -eu

replace_placeholder() {
  _placeholder=$1
  _value=$2
  _escaped=$(printf '%s' "$_value" | sed 's/[\\|&]/\\&/g')

  find /app/.next -type f \( -name '*.js' -o -name '*.html' \) 2>/dev/null | while IFS= read -r f; do
    if test -f "$f" && grep -q "$_placeholder" "$f" 2>/dev/null; then
      printf '[entrypoint] replacing %s in %s\n' "$_placeholder" "$f"
      sed -i "s|${_placeholder}|${_escaped}|g" "$f"
    fi
  done

  if test -f /app/server.js && grep -q "$_placeholder" /app/server.js 2>/dev/null; then
    printf '[entrypoint] replacing %s in server.js\n' "$_placeholder"
    sed -i "s|${_placeholder}|${_escaped}|g" /app/server.js
  fi
}

# API base URL
API_URL_VALUE="${API_BASE_URL:-${BACKEND_URL:-http://localhost:8080}}"
if [ -z "$API_URL_VALUE" ] || [ "$API_URL_VALUE" = '__NEXT_PUBLIC_API_BASE_URL__' ]; then
  API_URL_VALUE='http://localhost:8080'
fi
replace_placeholder '__NEXT_PUBLIC_API_BASE_URL__' "$API_URL_VALUE"
printf '[entrypoint] using NEXT_PUBLIC_API_BASE_URL=%s (set at runtime)\n' "$API_URL_VALUE"
export NEXT_PUBLIC_API_BASE_URL="$API_URL_VALUE"

# Quick Start mode - read from QUICK_START (single source of truth)
QUICK_START_VALUE="${QUICK_START:-false}"
replace_placeholder '__NEXT_PUBLIC_QUICK_START__' "$QUICK_START_VALUE"
printf '[entrypoint] using NEXT_PUBLIC_QUICK_START=%s (set at runtime)\n' "$QUICK_START_VALUE"
export NEXT_PUBLIC_QUICK_START="$QUICK_START_VALUE"

exec "$@"
