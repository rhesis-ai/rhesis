#!/bin/bash

set -e

# === CONFIGURATION ===
BOOTSTRAP_PROJECT_ID="provide your project id here"
BILLING_ACCOUNT_ID="provide your billing account id here"
SA_NAME="terraform-deployer"
SA_DISPLAY_NAME="Terraform Deployer"
KEY_OUTPUT_PATH="./terraform-deployer-key.json"
REGION="europe-west4"
TF_STATE_BUCKET="${BOOTSTRAP_PROJECT_ID}-tfstate"

# === DERIVED VARIABLES ===
SA_EMAIL="${SA_NAME}@${BOOTSTRAP_PROJECT_ID}.iam.gserviceaccount.com"

# === HELPER FUNCTIONS ===
function log_info() {
  echo -e "\033[0;34m🔵 INFO: $1\033[0m"
}

function log_success() {
  echo -e "\033[0;32m✅ SUCCESS: $1\033[0m"
}

function log_warning() {
  echo -e "\033[0;33m⚠️ WARNING: $1\033[0m"
}

function log_error() {
  echo -e "\033[0;31m❌ ERROR: $1\033[0m"
}

# Check if project exists
log_info "Checking if project exists..."
if ! gcloud projects describe "$BOOTSTRAP_PROJECT_ID" &>/dev/null; then
  log_error "Project $BOOTSTRAP_PROJECT_ID does not exist. Please create it first."
  exit 1
fi
log_success "Project $BOOTSTRAP_PROJECT_ID exists"

# Check and link billing account if needed
log_info "Checking billing account..."
BILLING_INFO=$(gcloud beta billing projects describe "$BOOTSTRAP_PROJECT_ID" --format="json" 2>/dev/null || echo '{"billingEnabled": false}')
BILLING_ENABLED=$(echo "$BILLING_INFO" | jq -r '.billingEnabled')

if [[ "$BILLING_ENABLED" != "true" ]]; then
  log_info "Linking billing account..."
  if gcloud beta billing projects link "$BOOTSTRAP_PROJECT_ID" --billing-account="$BILLING_ACCOUNT_ID"; then
    log_success "Billing linked to project: $BOOTSTRAP_PROJECT_ID"
  else
    log_error "Failed to link billing account. Please check your permissions and billing account ID."
    exit 1
  fi
else
  log_success "Billing already enabled for project: $BOOTSTRAP_PROJECT_ID"
fi

# Enable required APIs
log_info "Enabling required APIs..."
REQUIRED_APIS=(
  "cloudresourcemanager.googleapis.com"  # For project and organization management
  "iam.googleapis.com"                   # For IAM permissions
  "serviceusage.googleapis.com"          # For enabling other APIs
  "storage.googleapis.com"               # For GCS buckets
  "cloudbilling.googleapis.com"          # For billing account access
  "iamcredentials.googleapis.com"        # For service account credentials
  "sqladmin.googleapis.com"              # For Cloud SQL instances
  "compute.googleapis.com"               # For Compute Engine resources
  "run.googleapis.com"                   # For Cloud Run services
  "artifactregistry.googleapis.com"      # For container registry
  "pubsub.googleapis.com"                # For Pub/Sub topics
  "secretmanager.googleapis.com"         # For Secret Manager
  "logging.googleapis.com"               # For Cloud Logging
  "monitoring.googleapis.com"            # For Cloud Monitoring
  "dns.googleapis.com"                   # For Cloud DNS
  "servicenetworking.googleapis.com"     # For VPC peering with services
)

for api in "${REQUIRED_APIS[@]}"; do
  if ! gcloud services list --project="$BOOTSTRAP_PROJECT_ID" --filter="config.name:$api" --format="value(config.name)" | grep -q "$api"; then
    log_info "Enabling API: $api"
    gcloud services enable "$api" --project="$BOOTSTRAP_PROJECT_ID"
  else
    log_info "API already enabled: $api"
  fi
done

# Wait for APIs to be fully enabled
log_info "Waiting for APIs to be fully enabled..."
sleep 10
log_success "APIs enabled"

# Create service account if it doesn't exist
log_info "Checking if service account exists: $SA_NAME"
if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$BOOTSTRAP_PROJECT_ID" &>/dev/null; then
  log_info "Creating service account: $SA_NAME"
  gcloud iam service-accounts create "$SA_NAME" \
    --description="Service account for Terraform deployment" \
    --display-name="$SA_DISPLAY_NAME" \
    --project="$BOOTSTRAP_PROJECT_ID"
  log_success "Service account created: $SA_EMAIL"
else
  log_success "Service account already exists: $SA_EMAIL"
fi

# Get organization ID
log_info "Fetching organization ID..."
ORG_ID=$(gcloud organizations list --format="value(ID)" 2>/dev/null || echo "")

if [[ -z "$ORG_ID" ]]; then
  log_warning "Could not retrieve Organization ID. Are you in an org?"
  log_warning "Continuing without organization-level permissions."
  USING_ORG=false
else
  log_info "Organization ID: $ORG_ID"
  USING_ORG=true
fi

# Grant project-level roles
log_info "Granting project-level permissions to service account..."
PROJECT_ROLES=(
  "roles/viewer"
  "roles/serviceusage.serviceUsageAdmin"
  "roles/storage.admin"
  "roles/artifactregistry.admin"
  "roles/cloudsql.admin"
  "roles/run.admin"
)

for role in "${PROJECT_ROLES[@]}"; do
  log_info "Granting $role at project level..."
  gcloud projects add-iam-policy-binding "$BOOTSTRAP_PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="$role" \
    --quiet
done
log_success "Project-level roles granted"

# Grant org-level roles if in an organization
if [[ "$USING_ORG" == "true" ]]; then
  log_info "Granting org-level permissions to service account..."

  ORG_ROLES=(
    "roles/resourcemanager.projectCreator"
    "roles/billing.user"
    "roles/resourcemanager.folderViewer"
    "roles/iam.serviceAccountAdmin"
    "roles/iam.serviceAccountUser"
    "roles/serviceusage.serviceUsageAdmin"
  )

  for role in "${ORG_ROLES[@]}"; do
    log_info "Granting $role at organization level..."
    gcloud organizations add-iam-policy-binding "$ORG_ID" \
      --member="serviceAccount:$SA_EMAIL" \
      --role="$role" \
      --quiet
  done
  log_success "Organization-level roles granted"
else
  log_warning "Skipping organization-level permissions."
fi

# Create Terraform state bucket if it doesn't exist
log_info "Checking if Terraform state bucket exists: $TF_STATE_BUCKET"
if ! gcloud storage buckets describe "gs://${TF_STATE_BUCKET}" &>/dev/null; then
  log_info "Creating Terraform state bucket: $TF_STATE_BUCKET"
  gcloud storage buckets create "gs://${TF_STATE_BUCKET}" \
    --project="$BOOTSTRAP_PROJECT_ID" \
    --location="$REGION" \
    --uniform-bucket-level-access
  
  log_info "Setting bucket versioning..."
  gcloud storage buckets update "gs://${TF_STATE_BUCKET}" \
    --versioning
  
  log_success "Terraform state bucket created and configured"
else
  log_success "Terraform state bucket already exists: $TF_STATE_BUCKET"
  
  # Ensure versioning is enabled
  log_info "Ensuring bucket versioning is enabled..."
  gcloud storage buckets update "gs://${TF_STATE_BUCKET}" \
    --versioning
fi

# Grant bucket access to service account
log_info "Granting service account access to the state bucket..."
gcloud storage buckets add-iam-policy-binding "gs://${TF_STATE_BUCKET}" \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/storage.admin"

# Generate service account key if it doesn't exist
if [[ ! -f "$KEY_OUTPUT_PATH" ]]; then
  log_info "Generating and downloading service account key..."
  gcloud iam service-accounts keys create "$KEY_OUTPUT_PATH" \
    --iam-account="$SA_EMAIL"
  log_success "Key saved to $KEY_OUTPUT_PATH"
else
  log_warning "Key file already exists at $KEY_OUTPUT_PATH"
  read -p "Do you want to generate a new key? (y/N): " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    mv "$KEY_OUTPUT_PATH" "${KEY_OUTPUT_PATH}.$(date +%Y%m%d%H%M%S).bak"
    log_info "Old key backed up. Generating new key..."
    gcloud iam service-accounts keys create "$KEY_OUTPUT_PATH" \
      --iam-account="$SA_EMAIL"
    log_success "New key saved to $KEY_OUTPUT_PATH"
  fi
fi

log_success "Bootstrap completed. You can now use this key with Terraform."
log_info "Terraform backend configuration:"
echo "terraform {"
echo "  backend \"gcs\" {"
echo "    bucket = \"${TF_STATE_BUCKET}\""
echo "    prefix = \"terraform/environments/[ENV]\""
echo "  }"
echo "}"

log_info "Important reminders:"
echo "1. Make sure to enable the Cloud Billing API in any new projects created by Terraform"
echo "2. If you encounter permission issues, check the service account has the necessary roles"
echo "3. For production deployments, consider additional security measures for the state bucket"