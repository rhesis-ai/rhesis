#!/usr/bin/env bash
# Stop (and restart) hosted-model spend in an environment.
#
# Two levels, use the first one first:
#
#   app   Sets the hosted spend cap to 0 in Redis. The backend, workers and
#         chatbot refuse every call on our credentials within ~2s. Orgs on
#         their own keys keep working. Needs the hosted spend cap deployed
#         (HOSTED_MODEL_DAILY_BUDGET_USD set); this script checks.
#   gcp   Removes the Vertex roles from the service account the pods
#         authenticate as. Every Vertex call with our credentials fails with
#         403, whatever code path made it. IAM changes take up to a few
#         minutes to apply everywhere. Breaks Gemini for every user,
#         including the parts of the product that can't run without it.
#
# The service account is read from a running backend pod, so this follows
# credential changes without edits. gcp-off records the roles it removes
# (under ~/.local/state/rhesis/) and gcp-on restores exactly those.
#
# Usage:
#   hosted-model-kill-switch.sh [--env prd|stg|dev] status
#   hosted-model-kill-switch.sh [--env ...] app-off|app-on [--yes]
#   hosted-model-kill-switch.sh [--env ...] gcp-off|gcp-on [--yes]
#
# Without --yes, *-off and *-on only print what they would do.

set -euo pipefail

ENV_NAME="prd"
ACTION=""
APPLY=false
NAMESPACE="rhesis"
# What gcp-on grants when gcp-off left no record of the roles it removed.
DEFAULT_VERTEX_ROLE="roles/aiplatform.user"
CAP_KEY="hosted_spend:v1:cap_usd"
REDIS_DB=12  # RedisDatabase.HOSTED_SPEND

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env) ENV_NAME="$2"; shift 2 ;;
    --yes) APPLY=true; shift ;;
    status|app-off|app-on|gcp-off|gcp-on) ACTION="$1"; shift ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
[[ -n "$ACTION" ]] || { sed -n '2,25p' "$0"; exit 2; }

ROLES_FILE="${XDG_STATE_HOME:-$HOME/.local/state}/rhesis/kill-switch-$ENV_NAME.roles"

case "$ENV_NAME" in
  prd) CONTEXT="connectgateway_rhesis-prd_global_prd" ;;
  stg) CONTEXT="connectgateway_rhesis-stg-494712_global_stg" ;;
  dev) CONTEXT="connectgateway_rhesis-dev-494712_global_dev" ;;
  *) echo "Unknown env: $ENV_NAME" >&2; exit 2 ;;
esac

kc() { kubectl --context "$CONTEXT" -n "$NAMESPACE" "$@"; }

first_pod() {
  kc get pods -o name | grep -m1 "^pod/$1-" || { echo "No $1 pod in $ENV_NAME" >&2; exit 1; }
}

valkey() {
  local pod
  pod=$(kc get pods -o name | grep -m1 -E "^pod/rhesis-valkey-primary-0|^pod/.*valkey-primary") \
    || { echo "No Valkey primary pod in $ENV_NAME" >&2; exit 1; }
  kc exec "$pod" -- sh -c \
    'valkey-cli -a "$(cat "$VALKEY_PASSWORD_FILE")" --no-auth-warning -n '"$REDIS_DB"' "$@"' \
    valkey "$@"
}

vertex_sa() {
  kc exec "$(first_pod backend)" -- python3 -c '
import base64, json, os
v = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
info = json.loads(v) if v.startswith("{") else json.loads(base64.b64decode(v))
print(info["client_email"])'
}

sa_project() { local sa="$1"; sa="${sa#*@}"; echo "${sa%%.iam.gserviceaccount.com}"; }

sa_roles() {
  gcloud projects get-iam-policy "$2" --flatten='bindings[].members' \
    --filter="bindings.members:serviceAccount:$1" --format='value(bindings.role)'
}

run() {
  if $APPLY; then
    echo "+ $*"; "$@"
  else
    echo "[dry run] $*"
  fi
}

status() {
  local budget sa project today
  budget=$(kc get configmap rhesis-config -o jsonpath='{.data.HOSTED_MODEL_DAILY_BUDGET_USD}')
  today=$(date -u +%F)
  echo "Environment:        $ENV_NAME"
  echo "Budget (configmap): ${budget:-<unset: app-level cap NOT deployed>}"
  echo "Cap override:       $(valkey GET "$CAP_KEY" | sed 's/^$/<none>/')"
  echo "Spend today (USD):  $(valkey GET "hosted_spend:v1:$today" \
    | awk '{ if ($0 == "") print "0"; else printf "%.4f\n", $0 / 1000000 }')"
  sa=$(vertex_sa); project=$(sa_project "$sa")
  echo "Vertex account:     $sa"
  echo "Vertex roles:       $(sa_roles "$sa" "$project" | tr '\n' ' ' | sed 's/ $//;s/^$/<none: Vertex is off>/')"
}

case "$ACTION" in
  status) status ;;
  app-off)
    [[ -n "$(kc get configmap rhesis-config -o jsonpath='{.data.HOSTED_MODEL_DAILY_BUDGET_USD}')" ]] \
      || { echo "The hosted spend cap is not deployed in $ENV_NAME; use gcp-off." >&2; exit 1; }
    if $APPLY; then valkey SET "$CAP_KEY" 0; else echo "[dry run] SET $CAP_KEY 0 (db $REDIS_DB)"; fi
    ;;
  app-on)
    if $APPLY; then valkey DEL "$CAP_KEY"; else echo "[dry run] DEL $CAP_KEY (db $REDIS_DB)"; fi
    ;;
  gcp-off)
    sa=$(vertex_sa); project=$(sa_project "$sa")
    roles=$(sa_roles "$sa" "$project" | grep -E '^roles/aiplatform\.' || true)
    echo "Removing Vertex roles from $sa in $project: ${roles:-<none>}"
    # gcp-on restores exactly these.
    if $APPLY && [[ -n "$roles" ]]; then
      mkdir -p "$(dirname "$ROLES_FILE")"
      echo "$roles" > "$ROLES_FILE"
    fi
    for role in $roles; do
      run gcloud projects remove-iam-policy-binding "$project" \
        --member="serviceAccount:$sa" --role="$role" --condition=None --quiet
    done
    ;;
  gcp-on)
    sa=$(vertex_sa); project=$(sa_project "$sa")
    roles=$(cat "$ROLES_FILE" 2>/dev/null || echo "$DEFAULT_VERTEX_ROLE")
    echo "Restoring Vertex roles for $sa in $project: $roles"
    for role in $roles; do
      run gcloud projects add-iam-policy-binding "$project" \
        --member="serviceAccount:$sa" --role="$role" --condition=None --quiet
    done
    if $APPLY; then rm -f "$ROLES_FILE"; fi
    ;;
esac
