#!/usr/bin/env bash
set -euo pipefail

# Port-forward the Rhesis Postgres database (dev/stg/prd) to localhost so it can be
# opened in a local pgAdmin (or psql) client, then fetch the matching role's
# credentials from the cluster's Kubernetes secret.
#
# Usage:
#   bash infrastructure/scripts/db-connect.sh <dev|stg|prd> [admin|user|analytics] [options]
#
# Environments:
#   dev  - Bitnami PostgreSQL chart, single pod/service (not CNPG managed)
#   stg  - CloudNativePG cluster `rhesis-stg`
#   prd  - CloudNativePG cluster `rhesis-prd` (private endpoint)
#
# Prerequisites:
#   - kubectl installed and configured, WireGuard client connected (all three
#     GKE clusters restrict the API server to the WireGuard CIDR/IP).
#   - infrastructure/scripts/db-connect.env present (gitignored). Copy
#     infrastructure/scripts/db-connect.env.example to create it.
#
# See Notion: "Connecting to the Staging/Dev/Prod Database via pgAdmin"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/db-connect.env"

ROLE="user"
LOCAL_PORT="5433"
SWITCH_CONTEXT=true
PRINT_PASSWORD=false

show_usage() {
  cat <<EOF
Usage: bash $0 <dev|stg|prd> [admin|user|analytics] [options]

Roles (default: user - least privilege):
  admin      full access, bypasses RLS
  user       DML only (SELECT/INSERT/UPDATE/DELETE)
  analytics  analytics DB only

Options:
  --port PORT           local port to forward to (default: 5433)
  --no-context-switch    don't auto-switch the kubectl context
  --print-password       print the password instead of copying it to the clipboard
  -h, --help             show this help

Requires infrastructure/scripts/db-connect.env (gitignored) — copy
db-connect.env.example to create it.

Example:
  bash infrastructure/scripts/db-connect.sh stg admin
EOF
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: required command not found: $cmd"
    exit 1
  fi
}

decode_base64() {
  # GNU coreutils: --decode, macOS/BSD: -D
  if base64 --decode >/dev/null 2>&1 <<<""; then
    base64 --decode
  else
    base64 -D
  fi
}

cleanup() {
  if [[ -n "${PF_PID:-}" ]] && kill -0 "${PF_PID}" >/dev/null 2>&1; then
    echo ""
    echo "Stopping port-forward (pid ${PF_PID})..."
    kill "${PF_PID}" >/dev/null 2>&1 || true
  fi
}

# Look up a variable by name (populated by sourcing db-connect.env) and
# fail loudly if it's missing, instead of silently port-forwarding to nowhere.
get_cfg() {
  local var_name="$1" value
  value="${!var_name:-}"
  if [[ -z "${value}" ]]; then
    echo "Error: missing '${var_name}' in ${CONFIG_FILE}" >&2
    exit 1
  fi
  printf '%s' "${value}"
}

# Make sure kubectl is pointed at the right cluster. If the context already
# exists locally, just switch to it. Otherwise fall back to `gcloud container
# clusters get-credentials`, which fetches it and also sets it as current.
ensure_context() {
  local target_context="$1" project="$2" region="$3" cluster="$4"
  local current
  current="$(kubectl config current-context 2>/dev/null || true)"

  if [[ "${current}" == "${target_context}" ]]; then
    return
  fi

  if [[ "${SWITCH_CONTEXT}" == false ]]; then
    echo "Error: current kubectl context is '${current:-<none>}', expected '${target_context}'."
    echo "Run 'kubectl config use-context ${target_context}' or drop --no-context-switch."
    exit 1
  fi

  if kubectl config get-contexts "${target_context}" >/dev/null 2>&1; then
    echo "Switching kubectl context: ${current:-<none>} -> ${target_context}"
    kubectl config use-context "${target_context}"
  else
    echo "Context '${target_context}' not found locally; fetching it via gcloud..."
    require_cmd gcloud
    gcloud container clusters get-credentials "${cluster}" --region "${region}" --project "${project}"
  fi
}

main() {
  if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    show_usage
    exit 0
  fi
  if [[ $# -lt 1 ]]; then
    show_usage
    exit 1
  fi

  local env="$1"; shift
  case "${env}" in
    dev|stg|prd) ;;
    *) echo "Error: environment must be dev, stg, or prd"; exit 1 ;;
  esac

  if [[ $# -gt 0 && "$1" != --* ]]; then
    ROLE="$1"; shift
  fi
  case "${ROLE}" in
    admin|user|analytics) ;;
    *) echo "Error: role must be admin, user, or analytics"; exit 1 ;;
  esac

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --port) LOCAL_PORT="$2"; shift 2 ;;
      --no-context-switch) SWITCH_CONTEXT=false; shift ;;
      --print-password) PRINT_PASSWORD=true; shift ;;
      -h|--help) show_usage; exit 0 ;;
      *) echo "Error: unknown option: $1"; show_usage; exit 1 ;;
    esac
  done

  require_cmd kubectl
  require_cmd base64

  if [[ ! -f "${CONFIG_FILE}" ]]; then
    echo "Error: config file not found: ${CONFIG_FILE}"
    echo "Copy db-connect.env.example to db-connect.env and adjust if needed."
    exit 1
  fi
  # shellcheck disable=SC1090
  source "${CONFIG_FILE}"

  local env_upper
  env_upper="$(printf '%s' "${env}" | tr '[:lower:]' '[:upper:]')"

  local namespace project region cluster context svc db_name
  namespace="$(get_cfg NAMESPACE)"
  project="$(get_cfg "${env_upper}_PROJECT")"
  region="$(get_cfg "${env_upper}_REGION")"
  cluster="$(get_cfg "${env_upper}_CLUSTER")"
  context="$(get_cfg "${env_upper}_CONTEXT")"
  svc="$(get_cfg "${env_upper}_SVC")"
  if [[ "${ROLE}" == "analytics" ]]; then
    db_name="$(get_cfg "${env_upper}_ANALYTICS_DB_NAME")"
  else
    db_name="$(get_cfg "${env_upper}_DB_NAME")"
  fi

  # dev is a plain Bitnami Postgres pod (one shared secret, password-only keys,
  # fixed usernames); stg/prd are CNPG clusters (one secret per role, with both
  # username and password keys, managed by the CNPG operator).
  local secret_name secret_pass_key username=""
  if [[ "${env}" == "dev" ]]; then
    secret_name="$(get_cfg DEV_SECRET_NAME)"
    case "${ROLE}" in
      admin)     username="$(get_cfg DEV_ADMIN_USERNAME)";     secret_pass_key="$(get_cfg DEV_ADMIN_PASS_KEY)" ;;
      user)      username="$(get_cfg DEV_USER_USERNAME)";      secret_pass_key="$(get_cfg DEV_USER_PASS_KEY)" ;;
      analytics) username="$(get_cfg DEV_ANALYTICS_USERNAME)"; secret_pass_key="$(get_cfg DEV_ANALYTICS_PASS_KEY)" ;;
    esac
  else
    case "${ROLE}" in
      admin)     secret_name="$(get_cfg "${env_upper}_ADMIN_SECRET")" ;;
      user)      secret_name="$(get_cfg "${env_upper}_USER_SECRET")" ;;
      analytics) secret_name="$(get_cfg "${env_upper}_ANALYTICS_SECRET")" ;;
    esac
    secret_pass_key="password"
  fi

  ensure_context "${context}" "${project}" "${region}" "${cluster}"

  echo "Fetching credentials for role '${ROLE}' from secret '${secret_name}'..."
  if [[ -z "${username}" ]]; then
    username="$(kubectl -n "${namespace}" get secret "${secret_name}" -o jsonpath='{.data.username}' | decode_base64)"
  fi
  local password
  password="$(kubectl -n "${namespace}" get secret "${secret_name}" -o "jsonpath={.data.${secret_pass_key}}" | decode_base64)"

  if [[ -z "${username}" || -z "${password}" ]]; then
    echo "Error: empty username/password from secret ${secret_name}"
    exit 1
  fi

  trap cleanup EXIT INT TERM

  echo "Starting port-forward: svc/${svc} -> 127.0.0.1:${LOCAL_PORT}"
  kubectl -n "${namespace}" port-forward "svc/${svc}" "${LOCAL_PORT}:5432" >/tmp/rhesis-pgadmin-port-forward.log 2>&1 &
  PF_PID=$!
  sleep 3

  if ! kill -0 "${PF_PID}" >/dev/null 2>&1; then
    echo "Error: port-forward failed to start. Check /tmp/rhesis-pgadmin-port-forward.log"
    exit 1
  fi

  echo ""
  echo "pgAdmin connection details (${env}, role: ${ROLE}):"
  echo "  Host:                 localhost"
  echo "  Port:                 ${LOCAL_PORT}"
  echo "  Maintenance database:  ${db_name}"
  echo "  Username:              ${username}"
  if [[ "${PRINT_PASSWORD}" == false ]] && command -v pbcopy >/dev/null 2>&1; then
    printf '%s' "${password}" | pbcopy
    echo "  Password:              copied to clipboard"
  else
    echo "  Password:              ${password}"
  fi
  echo ""
  echo "Port-forward is running (pid ${PF_PID}). Leave this running while pgAdmin is open."
  echo "Press Ctrl+C to stop."

  wait "${PF_PID}"
}

main "$@"
