#!/bin/sh
# Replace the build-time placeholder in the Next.js bundle with the runtime
# public API URL before starting the standalone server.
#
# Resolution: API_BASE_URL (browser-facing) -> BACKEND_URL -> localhost default.
# The image is built with NEXT_PUBLIC_API_BASE_URL=__NEXT_PUBLIC_API_BASE_URL__
# inlined into the client bundle; this script rewrites that placeholder in
# compiled JS/HTML, then exports NEXT_PUBLIC_API_BASE_URL for the Node process
# (e.g. api-client/config.ts validation) without changing application source.

set -eu

PLACEHOLDER='__NEXT_PUBLIC_API_BASE_URL__'
RUNTIME_VALUE="${API_BASE_URL:-${BACKEND_URL:-http://localhost:8080}}"
if [ -z "$RUNTIME_VALUE" ] || [ "$RUNTIME_VALUE" = "$PLACEHOLDER" ]; then
  RUNTIME_VALUE='http://localhost:8080'
fi

# Escape &, |, \ for sed replacement (delimiter |)
ESCAPED=$(printf '%s' "$RUNTIME_VALUE" | sed 's/[\\|&]/\\&/g')

replace_if_match() {
  _f=$1
  if ! test -f "$_f"; then
    return 0
  fi
  if ! grep -q "$PLACEHOLDER" "$_f" 2>/dev/null; then
    return 0
  fi
  printf '[entrypoint] replacing placeholder in %s\n' "$_f"
  sed -i "s|${PLACEHOLDER}|${ESCAPED}|g" "$_f"
}

find /app/.next -type f \( -name '*.js' -o -name '*.html' \) 2>/dev/null | while IFS= read -r f; do
  replace_if_match "$f"
done

if test -f /app/server.js; then
  replace_if_match /app/server.js
fi

printf '[entrypoint] using NEXT_PUBLIC_API_BASE_URL=%s (set at runtime)\n' "$RUNTIME_VALUE"

export NEXT_PUBLIC_API_BASE_URL="$RUNTIME_VALUE"

exec "$@"
