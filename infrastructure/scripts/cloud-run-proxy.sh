#!/usr/bin/env bash
#
# Proxy localhost to the Rhesis documentation Cloud Run service (requires gcloud auth + run.invoker on dev/stg).
#
# Examples:
#   ./cloud-run-proxy.sh
#   ./cloud-run-proxy.sh docs
#   ./cloud-run-proxy.sh -e stg -r europe-west4
#   ./cloud-run-proxy.sh stop
#
set -euo pipefail

SCRIPT_NAME=$(basename "$0")
PIDFILE="${TMPDIR:-/tmp}/rhesis-cloud-run-proxy-docs.pids"
LOGDIR="${TMPDIR:-/tmp}/rhesis-cloud-run-proxy-logs"

DEFAULT_REGION="${GCP_REGION:-us-central1}"
DEFAULT_ENV="${RHESIS_ENV:-${ENVIRONMENT:-dev}}"
DEFAULT_PROJECT_ID="${GCP_PROJECT:-playground-437609}"


DOCS_LOCAL_PORT=3001

usage() {
  cat <<EOF
Usage: $SCRIPT_NAME [options] [command]

Proxies only the rhesis-docs Cloud Run service (same pattern as docs workflow: prd → rhesis-docs, else → rhesis-docs-<env>).

Commands:
  (default)   Same as docs — run proxy in foreground.
  docs        Run gcloud run services proxy for docs (foreground).
  all         Start docs proxy in the background (log under $LOGDIR).
  list        Print resolved service name and local port.
  stop        Stop background proxy if PID file exists ($PIDFILE).

Options:
  -p, --project ID   GCP project (default: $DEFAULT_PROJECT_ID)
  -r, --region NAME  Region (default: $DEFAULT_REGION)
  -e, --env NAME     dev | stg | prd (default: $DEFAULT_ENV)

Environment:
  GCP_PROJECT        Override default project when -p is omitted
  GCP_REGION, RHESIS_ENV or ENVIRONMENT — same as flags above.
EOF
}

resolve_project() {
  if [[ -n "${PROJECT_ID:-}" ]]; then
    echo "$PROJECT_ID"
    return
  fi
  echo "${GCP_PROJECT:-$DEFAULT_PROJECT_ID}"
}

docs_service_name() {
  local env=$1
  if [[ "$env" == "prd" ]]; then
    echo "rhesis-docs"
  else
    echo "rhesis-docs-${env}"
  fi
}

run_proxy_foreground() {
  local project=$1
  local region=$2
  local env=$3
  local name
  name=$(docs_service_name "$env")
  echo "→ proxy ${name} → http://127.0.0.1:${DOCS_LOCAL_PORT} (project=${project} region=${region})"
  exec gcloud run services proxy "$name" \
    --region="$region" \
    --project="$project" \
    --port="$DOCS_LOCAL_PORT"
}

cmd_list() {
  local project region env name
  project=$(resolve_project)
  region=$REGION
  env=$ENV
  name=$(docs_service_name "$env")

  echo "Project: $project  Region: $region  Environment: $env"
  echo ""
  echo "  docs → $name  (local port ${DOCS_LOCAL_PORT})"
}

cmd_all() {
  local project region env name logf
  project=$(resolve_project)
  region=$REGION
  env=$ENV
  name=$(docs_service_name "$env")

  mkdir -p "$LOGDIR"
  logf="${LOGDIR}/docs.log"

  echo "Starting docs proxy in background (log: $logf)"
  echo "  $name → http://127.0.0.1:${DOCS_LOCAL_PORT}"

  nohup gcloud run services proxy "$name" \
    --region="$region" \
    --project="$project" \
    --port="$DOCS_LOCAL_PORT" >>"$logf" 2>&1 &
  echo $! >"$PIDFILE"

  echo ""
  echo "PID saved to $PIDFILE"
  echo "Stop with: $SCRIPT_NAME stop"
}

cmd_stop() {
  if [[ ! -f "$PIDFILE" ]]; then
    echo "No PID file at $PIDFILE (nothing to stop)."
    exit 0
  fi
  while read -r pid; do
    [[ -z "$pid" ]] && continue
    if kill -0 "$pid" 2>/dev/null; then
      echo "Stopping PID $pid"
      kill "$pid" 2>/dev/null || true
    fi
  done <"$PIDFILE"
  rm -f "$PIDFILE"
  echo "Done."
}

PROJECT_ID=""
REGION="$DEFAULT_REGION"
ENV="$DEFAULT_ENV"
POSITIONAL=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p | --project)
      PROJECT_ID="${2:?}"
      shift 2
      ;;
    -r | --region)
      REGION="${2:?}"
      shift 2
      ;;
    -e | --env)
      ENV="${2:?}"
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done

case "$ENV" in
  dev | stg | prd) ;;
  *)
    echo "error: --env must be dev, stg, or prd (got: $ENV)" >&2
    exit 1
    ;;
esac

# Default command: docs (foreground)
if [[ ${#POSITIONAL[@]} -eq 0 ]]; then
  project=$(resolve_project)
  run_proxy_foreground "$project" "$REGION" "$ENV"
  exit 0
fi

COMMAND="${POSITIONAL[0]}"

case "$COMMAND" in
  list)
    cmd_list
    ;;
  all)
    cmd_all
    ;;
  stop)
    cmd_stop
    ;;
  docs)
    project=$(resolve_project)
    run_proxy_foreground "$project" "$REGION" "$ENV"
    ;;
  *)
    echo "error: unknown command '$COMMAND'. Use: docs | all | list | stop (or omit for docs)" >&2
    exit 1
    ;;
esac
