#!/bin/bash

set -e

# === USAGE ===
if [[ -z "$1" ]]; then
  echo "Usage: $0 <PROJECT_ID>"
  echo "Example: $0 playground-437609"
  exit 1
fi

# === CONFIGURATION ===
PROJECT_ID="$1"  # Target project for deployments
SA_PROJECT_ID="rhesis-platform-admin"  # Project where service account lives
SA_NAME="terraform-deployer"
SA_DISPLAY_NAME="Terraform Deployer Service Account"
KEY_OUTPUT_PATH="./service-account-key.json"

# === DERIVED VARIABLES ===
SA_EMAIL="${SA_NAME}@${SA_PROJECT_ID}.iam.gserviceaccount.com"

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
if ! gcloud projects describe "$PROJECT_ID" &>/dev/null; then
  log_error "Project $PROJECT_ID does not exist. Please create it first."
  exit 1
fi
log_success "Project $PROJECT_ID exists"

# Enable required APIs
log_info "Enabling required APIs..."
REQUIRED_APIS=(
  "cloudresourcemanager.googleapis.com"  # For project management
  "iam.googleapis.com"                   # For IAM permissions
  "serviceusage.googleapis.com"          # For enabling other APIs
  "aiplatform.googleapis.com"            # For Vertex AI endpoints
)

for api in "${REQUIRED_APIS[@]}"; do
  if ! gcloud services list --project="$PROJECT_ID" --filter="config.name:$api" --format="value(config.name)" | grep -q "$api"; then
    log_info "Enabling API: $api"
    gcloud services enable "$api" --project="$PROJECT_ID"
  else
    log_info "API already enabled: $api"
  fi
done

# Create service account if it doesn't exist
log_info "Checking if service account exists: $SA_NAME"
if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$SA_PROJECT_ID" &>/dev/null; then
  log_info "Creating service account: $SA_NAME"
  gcloud iam service-accounts create "$SA_NAME" \
    --description="Service account for GKE worker deployment" \
    --display-name="$SA_DISPLAY_NAME" \
    --project="$SA_PROJECT_ID"
  log_success "Service account created: $SA_EMAIL"
else
  log_success "Service account already exists: $SA_EMAIL"
fi

# Grant roles to service account
log_info "Granting roles to service account..."

# Required roles for GKE worker deployment
REQUIRED_ROLES=(
  "roles/container.admin"           # Kubernetes Engine Admin - for GKE cluster creation/management
  "roles/container.clusterAdmin"    # Kubernetes Engine Cluster Admin - specifically for cluster creation
  "roles/container.developer"       # Kubernetes Engine Developer - for additional GKE operations
  "roles/iam.serviceAccountUser"    # Service Account User - for GKE nodes to use service accounts  
  "roles/compute.networkAdmin"      # Compute Network Admin - for VPC networking
  "roles/compute.viewer"            # Compute Viewer - for viewing network resources
  "roles/aiplatform.user"           # Vertex AI User - for creating Vertex AI endpoints
)

for role in "${REQUIRED_ROLES[@]}"; do
  log_info "Adding role: $role"
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="$role" \
    --quiet
  log_success "Role added: $role"
done

# Generate service account key if it doesn't exist
if [[ ! -f "$KEY_OUTPUT_PATH" ]]; then
  log_info "Generating and downloading service account key..."
  gcloud iam service-accounts keys create "$KEY_OUTPUT_PATH" \
    --iam-account="$SA_EMAIL" \
    --project="$SA_PROJECT_ID"
  log_success "Key saved to $KEY_OUTPUT_PATH"
else
  log_warning "Key file already exists at $KEY_OUTPUT_PATH"
  read -p "Do you want to generate a new key? (y/N): " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    mv "$KEY_OUTPUT_PATH" "${KEY_OUTPUT_PATH}.$(date +%Y%m%d%H%M%S).bak"
    log_info "Old key backed up. Generating new key..."
    gcloud iam service-accounts keys create "$KEY_OUTPUT_PATH" \
      --iam-account="$SA_EMAIL" \
      --project="$SA_PROJECT_ID"
    log_success "New key saved to $KEY_OUTPUT_PATH"
  fi
fi

log_success "Service account bootstrap completed."
log_info "Important reminders:"
echo "1. Make sure to add the necessary roles for your use case"
echo "2. Keep the service account key secure and never commit it to version control"
echo "3. Consider using workload identity federation for production environments" 