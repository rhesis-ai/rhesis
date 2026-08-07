#!/bin/bash
# Generates a new key for the license-ci-<env> service account (created by
# terraform/infrastructure/modules/connect-gateway/gcp) and pushes it into
# the matching GitHub Environment secret (GCP_SA_KEY) in the private
# rhesis-ai/rhesis-ee repo, which is what license-issue.yml and
# license-mint-selfhosted.yml authenticate with.
#
# This is a one-off/rotation tool, run manually by a human -- not something
# any pipeline calls automatically. Run it once per environment after the
# connect-gateway module has been applied for that environment (the SA must
# already exist), and again whenever the key needs rotating.
#
# license-ci-<env> is deliberately scoped to only what these two workflows
# need (see the module's main.tf for the exact roles) -- unlike
# terraform-<env>, which holds roles/editor + iam.securityAdmin +
# resourcemanager.projectIamAdmin on the whole project and should never have
# a static key handed to a different repository's CI.
#
# Prerequisites:
#   - gcloud CLI authenticated with permission to create SA keys in the
#     target project (terraform-<env> or an equivalent admin identity)
#   - gh CLI authenticated with permission to set secrets on rhesis-ai/rhesis-ee
#   - terraform apply already run for the target environment (the SA must exist)
#
# Usage: ./rotate-license-ci-key.sh <dev|stg|prd>

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────

ENVIRONMENT="${1:-}"
EE_REPO="rhesis-ai/rhesis-ee"

if [[ -z "$ENVIRONMENT" ]]; then
  echo "Usage: $0 <dev|stg|prd>"
  exit 1
fi

case "$ENVIRONMENT" in
  dev) PROJECT_ID="rhesis-dev-494712" ;;
  stg) PROJECT_ID="rhesis-stg-494712" ;;
  prd) PROJECT_ID="rhesis-prd" ;;
  *)
    echo "Unknown environment '$ENVIRONMENT' -- expected dev, stg, or prd."
    exit 1
    ;;
esac

SA_EMAIL="license-ci-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"

# ── Colors & helpers ─────────────────────────────────────────────────

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()    { echo -e "🔵 $1"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error()   { echo -e "${RED}❌ $1${NC}"; }

# ── Verify the SA exists ─────────────────────────────────────────────

log_info "Checking $SA_EMAIL exists in $PROJECT_ID..."
if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
  log_error "$SA_EMAIL not found in $PROJECT_ID."
  log_error "Run terraform apply for envs/$ENVIRONMENT first (module.connect_gateway_$ENVIRONMENT creates it)."
  exit 1
fi
log_success "$SA_EMAIL exists"

# Existing keys are a lingering risk (nothing prunes them automatically) --
# surface the count so an operator notices if this has been rotated before
# without the old key ever being deleted.
EXISTING_KEYS=$(gcloud iam service-accounts keys list \
  --iam-account="$SA_EMAIL" \
  --managed-by=user \
  --format="value(name)" | wc -l | tr -d ' ')
if [[ "$EXISTING_KEYS" -gt 0 ]]; then
  log_warning "$EXISTING_KEYS existing user-managed key(s) on $SA_EMAIL."
  log_warning "Consider deleting the old key once the new one is confirmed working:"
  log_warning "  gcloud iam service-accounts keys list --iam-account=$SA_EMAIL"
  log_warning "  gcloud iam service-accounts keys delete <KEY_ID> --iam-account=$SA_EMAIL"
fi

# ── Generate the key and push it, without ever writing it to disk ──────

log_info "Generating a new key for $SA_EMAIL..."
KEY_JSON=$(gcloud iam service-accounts keys create /dev/stdout \
  --iam-account="$SA_EMAIL" \
  --project="$PROJECT_ID")
log_success "Key generated"

log_info "Pushing to $EE_REPO's '$ENVIRONMENT' GitHub Environment secret GCP_SA_KEY..."
echo "$KEY_JSON" | gh secret set GCP_SA_KEY --repo "$EE_REPO" --env "$ENVIRONMENT"
unset KEY_JSON
log_success "GCP_SA_KEY updated for $EE_REPO environment '$ENVIRONMENT'"

log_info "Done. The new key is live in GitHub; nothing was written to disk locally."
