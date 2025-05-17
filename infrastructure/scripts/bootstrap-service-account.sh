#!/bin/bash

set -e

# === CONFIGURATION ===
PROJECT_ID="your-project-id"
SA_NAME="your-service-account-name"
SA_DISPLAY_NAME="Your Service Account Display Name"
KEY_OUTPUT_PATH="./service-account-key.json"

# === DERIVED VARIABLES ===
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

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
if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
  log_info "Creating service account: $SA_NAME"
  gcloud iam service-accounts create "$SA_NAME" \
    --description="Service account for your use case" \
    --display-name="$SA_DISPLAY_NAME" \
    --project="$PROJECT_ID"
  log_success "Service account created: $SA_EMAIL"
else
  log_success "Service account already exists: $SA_EMAIL"
fi

# Grant roles to service account
log_info "Granting roles to service account..."
# Add your required roles here, for example:
# gcloud projects add-iam-policy-binding "$PROJECT_ID" \
#   --member="serviceAccount:$SA_EMAIL" \
#   --role="roles/your.required.role" \
#   --quiet

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

log_success "Service account bootstrap completed."
log_info "Important reminders:"
echo "1. Make sure to add the necessary roles for your use case"
echo "2. Keep the service account key secure and never commit it to version control"
echo "3. Consider using workload identity federation for production environments" 