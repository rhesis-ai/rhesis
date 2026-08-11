#!/usr/bin/env bash
#
# Fails if any env var key is declared in both the rendered Helm ConfigMap and
# the cluster ExternalSecret for the same environment. secretRef is listed
# after configMapRef in every deployment's envFrom, so a duplicate key means
# the Secret silently overrides the chart and values-*.yaml edits become
# no-ops with no warning.
#
# Used by the `kubernetes` job in .github/workflows/lint.yml.
# Locally: scripts/check-k8s-secret-overlap.sh

set -euo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

FAILED=0

for env in dev stg prd; do
  secrets_file="kubernetes/clusters/$env/external-secrets/rhesis-app-secrets.yaml"
  cm_keys=$(
    helm template rhesis charts/rhesis -f "charts/rhesis/values-$env.yaml" \
      | awk '/kind: ConfigMap/,/^---/' \
      | grep -oE '^  [A-Z][A-Z0-9_]+:' | tr -d ' :' | sort -u
  )
  secret_keys=$(
    grep -oE 'secretKey: [A-Z][A-Z0-9_]+' "$secrets_file" \
      | awk '{print $2}' | sort -u
  )
  overlap=$(comm -12 <(echo "$cm_keys") <(echo "$secret_keys"))
  if [[ -n "$overlap" ]]; then
    echo "[$env] key(s) declared in both the ConfigMap and $secrets_file:" >&2
    echo "$overlap" | sed 's/^/  /' >&2
    FAILED=1
  else
    echo "[$env] OK: no overlap between ConfigMap and ExternalSecret."
  fi
done

if [[ "$FAILED" -ne 0 ]]; then
  echo "Move the duplicated key(s) to a single source: ConfigMap for non-secret config, ExternalSecret for secrets." >&2
  exit 1
fi
