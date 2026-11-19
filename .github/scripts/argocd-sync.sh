#!/usr/bin/env bash
# Sync an ArgoCD Application and wait for it to be healthy. With SERVICE set,
# only that service's Deployment is synced and waited on.
#
# Env: APP, SERVICE (values key, empty = whole app), ARGOCD_SERVER, ARGOCD_AUTH_TOKEN
set -euo pipefail

: "${APP:?}" "${ARGOCD_SERVER:?}" "${ARGOCD_AUTH_TOKEN:?}"

# Values key (camelCase) → Deployment name. workers[0] is worker-default, the
# only worker type today; add more here if workers[1..] ever appear.
case "${SERVICE:-}" in
  otelCollector)      DEPLOY_NAME="otel-collector" ;;
  telemetryProcessor) DEPLOY_NAME="telemetry-processor" ;;
  workers)            DEPLOY_NAME="worker-default" ;;
  "")                 DEPLOY_NAME="" ;;
  *)                  DEPLOY_NAME="$SERVICE" ;;
esac
RESOURCE=()
if [ -n "$DEPLOY_NAME" ]; then
  RESOURCE=(--resource "apps:Deployment:$DEPLOY_NAME")
  echo "Targeting apps:Deployment:$DEPLOY_NAME"
else
  echo "Targeting the whole application"
fi

argo() {
  argocd "$@" --server "$ARGOCD_SERVER" --auth-token "$ARGOCD_AUTH_TOKEN" --grpc-web
}

# Setting the tags starts ArgoCD's own auto-sync, so "another operation" is
# expected. ComparisonError / deadline errors are ArgoCD failing to compute
# health in time (nightly deploy-all, 2026-11-19), not a bad deploy. Between
# attempts, wait on the in-flight operation itself rather than a fixed sleep:
# run 34803006754 gave up after 5x30s while the blocking operation finished 7s
# later.
for attempt in $(seq 1 5); do
  EXIT_CODE=0
  OUTPUT=$(argo app sync "$APP" --timeout 300 "${RESOURCE[@]}" 2>&1) || EXIT_CODE=$?
  echo "$OUTPUT"
  [ "$EXIT_CODE" -eq 0 ] && break
  if ! grep -qiE "another operation|ComparisonError|context deadline exceeded" <<<"$OUTPUT"; then
    echo "Non-retryable error — failing fast."
    exit 1
  fi
  if [ "$attempt" -eq 5 ]; then
    echo "All 5 sync attempts failed."
    exit 1
  fi
  echo "Attempt $attempt failed (concurrent operation) — waiting for it to finish..."
  argo app wait "$APP" --operation --timeout 600 || true
done

argo app wait "$APP" --health --timeout 1200 "${RESOURCE[@]}"
