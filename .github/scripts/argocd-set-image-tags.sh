#!/usr/bin/env bash
# Set image tag parameters on an ArgoCD Application, atomically.
#
# Writes through the Kubernetes API, not `argocd app set`. ArgoCD applies
# set/patch by writing back a spec it read earlier, so two deploys that overlap
# lose one tag (seen on 2026-11-18). Here the JSON patch starts with a `test`
# op on the current helm block, which the API server applies atomically: if
# another deploy changed it first, the patch is rejected and retried on a
# fresh read.
#
# Env:
#   APP          Application name (in namespace argocd)
#   TAG          image tag to set
#   SERVICE      values key (backend, workers, frontend, ...); empty = every
#                deploy-all service
#   ENVIRONMENT  dev | stg | prd (for error messages)
#   EVENT        github.event_name; only workflow_dispatch may move a tag back
#   REPO, GH_TOKEN  for the GitHub compare API
#   GATEWAY, ACCESS_TOKEN  optional; when set, a kubeconfig for that API server
#                is written. Otherwise the current kubeconfig is used.
#   DRY_RUN=1    optional; patch with --dry-run=server (for local testing)
set -euo pipefail

: "${APP:?}" "${TAG:?}" "${ENVIRONMENT:?}" "${EVENT:?}" "${REPO:?}"
SERVICE="${SERVICE:-}"

# global.imageTag can't be used for deploy-all: the chart resolves
# coalesce(<svc>.image.tag, global.imageTag), and per-service parameters from
# earlier deploys would shadow it. workers is a Helm list, hence workers[0].
# chatbot is excluded (9GB image, deployed by chatbot-k8s.yml).
# Keep this list in sync with the build jobs in deploy-all-k8s.yml.
case "$SERVICE" in
  "") KEYS='["backend.image.tag","frontend.image.tag","docs.image.tag","polyphemus.image.tag","otelCollector.image.tag","telemetryProcessor.image.tag","workers[0].image.tag"]' ;;
  workers) KEYS='["workers[0].image.tag"]' ;;
  *) KEYS=$(jq -nc --arg s "$SERVICE" '[$s + ".image.tag"]') ;;
esac

if [ -n "${GATEWAY:-}" ]; then
  export KUBECONFIG="${RUNNER_TEMP:-/tmp}/kubeconfig"
  install -m 600 /dev/null "$KUBECONFIG"
  cat > "$KUBECONFIG" <<EOF
apiVersion: v1
kind: Config
clusters: [{name: gateway, cluster: {server: "$GATEWAY"}}]
users: [{name: deploy-ci, user: {token: "$ACCESS_TOKEN"}}]
contexts: [{name: gateway, context: {cluster: gateway, user: deploy-ci}}]
current-context: gateway
EOF
fi

PATCH_ARGS=()
[ "${DRY_RUN:-}" = 1 ] && PATCH_ARGS+=(--dry-run=server)

rbac_error() {
  echo "::error::deploy-ci-$ENVIRONMENT can't read or patch $APP. Its Role is kubernetes/clusters/$ENVIRONMENT/argocd/rhesis-deployer-rbac.yaml; prd only has it once [Release] 3 Publish has promoted a commit that includes it."
  exit 1
}

# A rerun of an old push, or a slow run finishing late, must not roll a service
# back. Manual dispatches may: that's how you roll back on purpose.
is_older() {
  local new="$1" cur="$2" status
  [ "$EVENT" = workflow_dispatch ] && return 1
  [[ "$new" =~ ^[0-9a-f]{7,40}$ && "$cur" =~ ^[0-9a-f]{7,40}$ ]] || return 1
  status=$(curl -fsS -H "Authorization: Bearer ${GH_TOKEN:-}" \
    "https://api.github.com/repos/$REPO/compare/$cur...$new" | jq -r .status) || return 1
  [ "$status" = behind ]
}

for attempt in $(seq 1 10); do
  APP_JSON=$(kubectl -n argocd get application "$APP" -o json 2>&1) || { echo "$APP_JSON"; rbac_error; }
  HELM=$(jq -c '.spec.source.helm' <<<"$APP_JSON")

  WRITE='[]'
  while IFS= read -r KEY; do
    CUR=$(jq -r --arg k "$KEY" '(.parameters // [])[] | select(.name == $k) | .value' <<<"$HELM")
    if [ -n "$CUR" ] && is_older "$TAG" "$CUR"; then
      echo "::warning::$KEY is already at $CUR, which is newer than $TAG. Leaving it."
      continue
    fi
    WRITE=$(jq -c --arg k "$KEY" '. + [$k]' <<<"$WRITE")
  done < <(jq -r '.[]' <<<"$KEYS")
  if [ "$WRITE" = '[]' ]; then
    echo "Nothing to change."
    exit 0
  fi

  PARAMS=$(jq -c --argjson keys "$WRITE" --arg tag "$TAG" '
    reduce $keys[] as $k ((.parameters // []);
      if any(.[]; .name == $k)
      then map(if .name == $k then .value = $tag | .forceString = true else . end)
      else . + [{name: $k, value: $tag, forceString: true}]
      end)' <<<"$HELM")
  PATCH=$(jq -nc --argjson helm "$HELM" --argjson params "$PARAMS" \
    '[{op: "test", path: "/spec/source/helm", value: $helm},
      {op: "add", path: "/spec/source/helm/parameters", value: $params}]')

  if OUT=$(kubectl -n argocd patch application "$APP" --type json -p "$PATCH" "${PATCH_ARGS[@]}" 2>&1); then
    echo "$OUT"
    jq -r --arg tag "$TAG" '.[] | "  \(.) = \($tag)"' <<<"$WRITE"
    exit 0
  fi
  echo "$OUT"
  if grep -qiE 'forbidden|unauthorized|not ?found' <<<"$OUT"; then rbac_error; fi
  echo "The Application changed under us (attempt $attempt); retrying on a fresh read."
  sleep $((RANDOM % 3 + 1))
done
echo "::error::Gave up after 10 attempts."
exit 1
