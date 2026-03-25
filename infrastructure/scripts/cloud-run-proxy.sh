#!/usr/bin/env bash
#
# Proxy local ports to Rhesis Cloud Run services (requires authenticated gcloud + run.invoker).
#
# Examples:
#   ./cloud-run-proxy.sh frontend   # project defaults to playground-437609
#   ./cloud-run-proxy.sh -p other-project -e dev docs
#   ./cloud-run-proxy.sh all
#   ./cloud-run-proxy.sh stop
#
set -euo pipefail

SCRIPT_NAME=$(basename "$0")
PIDFILE="${TMPDIR:-/tmp}/rhesis-cloud-run-proxy.pids"
LOGDIR="${TMPDIR:-/tmp}/rhesis-cloud-run-proxy-logs"

DEFAULT_REGION="${GCP_REGION:-us-central1}"
DEFAULT_ENV="${RHESIS_ENV:-${ENVIRONMENT:-dev}}"
DEFAULT_PROJECT_ID="playground-437609"

ALL_KEYS="frontend docs chatbot polyphemus"

service_slug() {
  case "$1" in
    frontend) echo frontend ;;
    docs) echo docs ;;
    chatbot) echo chatbot ;;
    polyphemus) echo polyphemus ;;
    *) return 1 ;;
  esac
}

service_port() {
  case "$1" in
    frontend) echo 3000 ;;
    docs) echo 3001 ;;
    chatbot) echo 8080 ;;
    polyphemus) echo 8081 ;; # distinct local port when using "all"
    *) return 1 ;;
  esac
}

usage() {
  cat <<EOF
Usage: $SCRIPT_NAME [options] <command>

Commands:
  <service>   Run gcloud run services proxy for one service (foreground).
  all         Start proxies for every service in the background (unique local ports).
  list        Print Cloud Run service names and local ports used by this script.
  stop        Stop background proxies recorded in $PIDFILE

Services (short name → Cloud Run name pattern rhesis-<type>[-<env>]):
  frontend    local port 3000
  docs        local port 3001
  chatbot     local port 8080
  polyphemus  local port 8081  (distinct from chatbot when using "all")

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

cloud_run_service_name() {
  local key=$1
  local env=$2
  local slug
  slug=$(service_slug "$key") || {
    echo "error: unknown service key '$key'" >&2
    exit 1
  }
  if [[ "$env" == "prd" ]]; then
    echo "rhesis-${slug}"
  else
    echo "rhesis-${slug}-${env}"
  fi
}

is_valid_key() {
  local k=$1
  for x in $ALL_KEYS; do
    [[ "$x" == "$k" ]] && return 0
  done
  return 1
}

run_proxy() {
  local service=$1
  local port=$2
  local project=$3
  local region=$4

  echo "→ proxy ${service} → http://127.0.0.1:${port} (project=${project} region=${region})"
  exec gcloud run services proxy "$service" \
    --region="$region" \
    --project="$project" \
    --port="$port"
}

cmd_list() {
  local project region env name port
  project=$(resolve_project)
  region=$REGION
  env=$ENV

  echo "Project: $project  Region: $region  Environment: $env"
  echo ""
  for key in $ALL_KEYS; do
    name=$(cloud_run_service_name "$key" "$env")
    port=$(service_port "$key")
    echo "  $key → $name  (local port ${port})"
  done
}

cmd_all() {
  local project region env name port logf
  project=$(resolve_project)
  region=$REGION
  env=$ENV

  mkdir -p "$LOGDIR"
  : >"$PIDFILE"

  echo "Starting Cloud Run proxies in background (logs under $LOGDIR)"
  for key in $ALL_KEYS; do
    name=$(cloud_run_service_name "$key" "$env")
    port=$(service_port "$key")
    logf="${LOGDIR}/${key}.log"
    echo "  $name → http://127.0.0.1:${port} (log: $logf)"
    nohup gcloud run services proxy "$name" \
      --region="$region" \
      --project="$project" \
      --port="$port" >>"$logf" 2>&1 &
    echo $! >>"$PIDFILE"
  done

  echo ""
  echo "PIDs saved to $PIDFILE"
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

if [[ ${#POSITIONAL[@]} -eq 0 ]]; then
  usage
  exit 1
fi

COMMAND="${POSITIONAL[0]}"

case "$ENV" in
  dev | stg | prd) ;;
  *)
    echo "error: --env must be dev, stg, or prd (got: $ENV)" >&2
    exit 1
    ;;
esac

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
  *)
    key="$COMMAND"
    if ! is_valid_key "$key"; then
      echo "error: unknown service '$key'. Use: $ALL_KEYS | all | list | stop" >&2
      exit 1
    fi
    project=$(resolve_project)
    name=$(cloud_run_service_name "$key" "$ENV")
    port=$(service_port "$key")
    run_proxy "$name" "$port" "$project" "$REGION"
    ;;
esac
