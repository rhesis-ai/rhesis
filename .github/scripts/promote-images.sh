#!/usr/bin/env bash
# Copy the release's images from stg's registry to prd's, unchanged.
#
# prd runs exactly what stg tested: same digests, no rebuild. This works
# because no image build depends on the environment (k8s-build-push.yml only
# picks the registry). Fails if stg doesn't have an image for this tag, which
# means the release branch's stg deploy didn't finish.
#
# Env:
#   TAG                 image tag (short release commit)
#   SRC_REGISTRY        e.g. europe-west4-docker.pkg.dev/<stg project>/rhesis
#   DST_REGISTRY        e.g. europe-west4-docker.pkg.dev/<prd project>/rhesis
#   ACCESS_TOKEN        OAuth token that can read SRC and write DST
#   DRY_RUN=1           optional; check and print, copy nothing
set -euo pipefail

: "${TAG:?}" "${SRC_REGISTRY:?}" "${DST_REGISTRY:?}" "${ACCESS_TOKEN:?}"

# The deploy-all service list (chatbot is deployed on its own); keep it in sync
# with argocd-set-image-tags.sh and deploy-all-k8s.yml.
IMAGES=(rhesis-backend rhesis-worker rhesis-frontend rhesis-docs rhesis-polyphemus
        rhesis-otel-collector rhesis-telemetry-processor)

DOCKER_CONFIG="$(mktemp -d)"
export DOCKER_CONFIG
trap 'rm -rf "$DOCKER_CONFIG"' EXIT
crane auth login "${SRC_REGISTRY%%/*}" -u oauth2accesstoken --password-stdin <<<"$ACCESS_TOKEN" > /dev/null

for img in "${IMAGES[@]}"; do
  src="$SRC_REGISTRY/$img:$TAG"
  dst="$DST_REGISTRY/$img:$TAG"
  if ! digest=$(crane digest "$src" 2>&1); then
    echo "::error::$src not found ($digest). Did the release branch's stg deploy finish for this commit?"
    exit 1
  fi
  if [ "${DRY_RUN:-}" = 1 ]; then
    echo "would copy $src ($digest)"
    continue
  fi
  crane copy "$src" "$dst"
  copied=$(crane digest "$dst")
  if [ "$copied" != "$digest" ]; then
    echo "::error::$dst has digest $copied, expected $digest."
    exit 1
  fi
  echo "$img:$TAG  $digest"
done
