#!/usr/bin/env bash
# Set image tag parameters (and optionally the chart revision) on an ArgoCD
# Application, atomically.
#
# Writes through the Kubernetes API, not `argocd app set`. ArgoCD applies
# set/patch by writing back a spec it read earlier, so two deploys that overlap
# lose one tag (seen on 2026-11-18). Here the JSON patch starts with a `test`
# op on the current source block, which the API server applies atomically: if
# another deploy changed it first, the patch is rejected and retried on a
# fresh read.
#
# With REVISION, the chart's targetRevision is set in the same patch, so the
# chart and the images it was released with change in one sync (stg and prd;
# their root apps ignore this field so selfHeal doesn't put it back).
#
# Env:
#   APP          Application name (in namespace argocd)
#   TAG          image tag to set
#   SERVICE      values key (backend, workers, frontend, ...); empty = every
#                deploy-all service
#   REVISION     optional; git commit to pin the chart to
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
  echo "::error::deploy-ci-$ENVIRONMENT can't read or patch $APP. Its Role is kubernetes/clusters/$ENVIRONMENT/argocd/rhesis-deployer-rbac.yaml; prd only has it once [Release] 3 Deploy and publish has promoted a commit that includes it."
  exit 1
}

# A rerun of an old push, or a slow run finishing late, must not roll a service
# back. Manual dispatches may: that's how you roll back on purpose. If the order
# can't be checked, stop rather than guess.
is_older() {  # is_older <new> <current> <what, for messages>
  local new="$1" cur="$2" what="$3" status auth=()
  [ "$EVENT" = workflow_dispatch ] && return 1
  [[ "$new" =~ ^[0-9a-f]{7,40}$ && "$cur" =~ ^[0-9a-f]{7,40}$ ]] || return 1
  [ -n "${GH_TOKEN:-}" ] && auth=(-H "Authorization: Bearer $GH_TOKEN")
  if ! status=$(curl -fsS --retry 3 ${auth[@]+"${auth[@]}"} \
      "https://api.github.com/repos/$REPO/compare/$cur...$new" | jq -er .status); then
    echo "::error::Couldn't compare $cur and $new, so can't tell whether $new would roll $what back."
    exit 1
  fi
  if [ "$status" = behind ]; then
    echo "::warning::$what is already at $cur, which is newer than $new. Leaving it."
    return 0
  fi
  return 1
}

ERR="$(mktemp)"
trap 'rm -f "$ERR"' EXIT

for attempt in $(seq 1 10); do
  if ! APP_JSON=$(kubectl -n argocd get application "$APP" -o json 2>"$ERR"); then
    cat "$ERR"
    if grep -qiE 'forbidden|unauthorized|not ?found' "$ERR"; then rbac_error; fi
    echo "Reading $APP failed (attempt $attempt); retrying."
    sleep $((RANDOM % 3 + 1))
    continue
  fi
  SOURCE=$(jq -c '.spec.source' <<<"$APP_JSON")
  OPS='[]'

  WRITE='[]'
  while IFS= read -r KEY; do
    CUR=$(jq -r --arg k "$KEY" '(.helm.parameters // [])[] | select(.name == $k) | .value' <<<"$SOURCE")
    if [ -n "$CUR" ] && is_older "$TAG" "$CUR" "$KEY"; then continue; fi
    WRITE=$(jq -c --arg k "$KEY" '. + [$k]' <<<"$WRITE")
  done < <(jq -r '.[]' <<<"$KEYS")
  if [ "$WRITE" != '[]' ]; then
    PARAMS=$(jq -c --argjson keys "$WRITE" --arg tag "$TAG" '
      reduce $keys[] as $k ((.helm.parameters // []);
        if any(.[]; .name == $k)
        then map(if .name == $k then .value = $tag | .forceString = true else . end)
        else . + [{name: $k, value: $tag, forceString: true}]
        end)' <<<"$SOURCE")
    OPS=$(jq -c --argjson p "$PARAMS" '. + [{op: "add", path: "/spec/source/helm/parameters", value: $p}]' <<<"$OPS")
  fi

  CUR_REV=$(jq -r '.targetRevision' <<<"$SOURCE")
  if [ -n "${REVISION:-}" ] && [ "$REVISION" != "$CUR_REV" ] \
      && ! is_older "$REVISION" "$CUR_REV" "the chart revision"; then
    OPS=$(jq -c --arg r "$REVISION" '. + [{op: "add", path: "/spec/source/targetRevision", value: $r}]' <<<"$OPS")
  fi

  if [ "$OPS" = '[]' ]; then
    echo "Nothing to change."
    exit 0
  fi
  PATCH=$(jq -c --argjson src "$SOURCE" '[{op: "test", path: "/spec/source", value: $src}] + .' <<<"$OPS")

  if OUT=$(kubectl -n argocd patch application "$APP" --type json -p "$PATCH" ${PATCH_ARGS[@]+"${PATCH_ARGS[@]}"} 2>&1); then
    echo "$OUT"
    jq -r --arg tag "$TAG" '.[] | "  \(.) = \($tag)"' <<<"$WRITE"
    if jq -e 'any(.[]; .path == "/spec/source/targetRevision")' <<<"$OPS" > /dev/null; then
      echo "  chart revision = $REVISION"
    fi
    exit 0
  fi
  echo "$OUT"
  if grep -qiE 'forbidden|unauthorized|not ?found' <<<"$OUT"; then rbac_error; fi
  echo "The Application changed under us (attempt $attempt); retrying on a fresh read."
  sleep $((RANDOM % 3 + 1))
done
echo "::error::Gave up after 10 attempts."
exit 1
