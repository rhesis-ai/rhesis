#!/bin/bash
set -e

# Default values
ENV="dev"
AUTO_APPROVE=false
PLAN_ONLY=false
INIT_ONLY=false
SERVICE_ACCOUNT_KEY=""
FORCE_UNLOCK=""
STAGE="all"  # New parameter for staged deployment

# Function to display usage information
function show_usage() {
  echo "Usage: $0 [OPTIONS]"
  echo "Deploy Terraform infrastructure to specified environment"
  echo ""
  echo "Options:"
  echo "  -e, --environment ENV   Environment to deploy (dev, stg, prd) [default: dev]"
  echo "  -k, --key FILE          Path to GCP service account key JSON file [required]"
  echo "  -y, --auto-approve      Auto-approve Terraform apply"
  echo "  -p, --plan              Generate plan only, don't apply"
  echo "  -i, --init              Initialize Terraform only"
  echo "  -u, --force-unlock ID   Force unlock the state with the given lock ID"
  echo "  -s, --stage STAGE       Deployment stage (project, services, all) [default: all]"
  echo "  -h, --help              Show this help message"
  echo ""
  echo "Example:"
  echo "  $0 --environment stg --key ./terraform-deployer-key.json"
  echo "  $0 --environment dev --key ./terraform-deployer-key.json --stage project"
  echo "  $0 --environment dev --key ./terraform-deployer-key.json --stage services"
}

# Function to import existing service accounts into Terraform state
function import_service_accounts() {
  local project_id="rhesis-$ENV"
  local environment_var
  local cred_file="$(realpath "$SERVICE_ACCOUNT_KEY")"
  
  # Map environment to environment variable used in Terraform
  case "$ENV" in
    dev)
      environment_var="development"
      ;;
    stg)
      environment_var="staging"
      ;;
    prd)
      environment_var="production"
      ;;
  esac
  
  echo "🔍 Checking for existing service accounts in project $project_id..."
  
  # List of services to check
  local services=("backend" "frontend" "worker" "polyphemus" "chatbot")
  
  # Check if the project exists
  if ! gcloud projects describe "$project_id" --credential-file-override="$cred_file" &>/dev/null; then
    echo "ℹ️ Project $project_id does not exist yet. Skipping service account import."
    return 0
  fi
  
  # List all service accounts in the project to help with debugging
  echo "📋 Listing all service accounts in project $project_id:"
  gcloud iam service-accounts list --project="$project_id" --credential-file-override="$cred_file" --format="table(email,displayName)" || {
    echo "⚠️ Warning: Could not list service accounts. Continuing with import attempt."
  }
  
  for service in "${services[@]}"; do
    # Use the exact naming pattern from the Terraform code:
    # In IAM module: locals { service_account_id = "svc-${var.service_name}-${var.environment}" }
    local sa_id="svc-${service}-${environment_var}"
    local sa_email="${sa_id}@${project_id}.iam.gserviceaccount.com"
    local resource_address="module.${ENV}_environment.module.${service}.module.service_sa.google_service_account.service_account[0]"
    
    echo "🔍 Checking for service account: $sa_email"
    
    # Check if the service account exists in GCP
    if gcloud iam service-accounts describe "$sa_email" --project="$project_id" --credential-file-override="$cred_file" &>/dev/null; then
      echo "✅ Found existing service account: $sa_email"
      
      # Check if it's already in the Terraform state
      if ! terraform state list "$resource_address" &>/dev/null; then
        echo "🔄 Importing service account into Terraform state: $sa_email"
        terraform import "$resource_address" "projects/${project_id}/serviceAccounts/${sa_email}"
        echo "✅ Successfully imported service account: $sa_email"
      else
        echo "ℹ️ Service account already in Terraform state: $sa_email"
      fi
    else
      echo "ℹ️ Service account does not exist in GCP: $sa_email"
    fi
  done
  
  echo "✅ Service account import process completed"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    -e|--environment)
      ENV="$2"
      shift 2
      ;;
    -k|--key)
      SERVICE_ACCOUNT_KEY="$2"
      shift 2
      ;;
    -y|--auto-approve)
      AUTO_APPROVE=true
      shift
      ;;
    -p|--plan)
      PLAN_ONLY=true
      shift
      ;;
    -i|--init)
      INIT_ONLY=true
      shift
      ;;
    -u|--force-unlock)
      FORCE_UNLOCK="$2"
      shift 2
      ;;
    -s|--stage)
      STAGE="$2"
      shift 2
      ;;
    -h|--help)
      show_usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      show_usage
      exit 1
      ;;
  esac
done

# Validate stage parameter
if [[ "$STAGE" != "all" && "$STAGE" != "project" && "$STAGE" != "services" ]]; then
  echo "❌ Invalid stage: $STAGE"
  echo "Valid stages: all, project, services"
  exit 1
fi

# Validate environment
if [[ "$ENV" != "dev" && "$ENV" != "stg" && "$ENV" != "prd" ]]; then
  echo "❌ Invalid environment: $ENV"
  echo "Valid environments: dev, stg, prd"
  exit 1
fi

# Check for required service account key
if [[ -z "$SERVICE_ACCOUNT_KEY" ]]; then
  echo "❌ Service account key file is required"
  show_usage
  exit 1
fi

if [[ ! -f "$SERVICE_ACCOUNT_KEY" ]]; then
  echo "❌ Service account key file not found: $SERVICE_ACCOUNT_KEY"
  exit 1
fi

# Map environment to directory
case "$ENV" in
  dev)
    ENV_DIR="development"
    ENV_PATH="environments/dev"
    ;;
  stg)
    ENV_DIR="staging"
    ENV_PATH="environments/stg"
    ;;
  prd)
    ENV_DIR="production"
    ENV_PATH="environments/prd"
    ;;
esac

# Navigate to the project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Navigate to the environment directory
cd "$ENV_PATH"

# Set up GCP authentication
echo "🔑 Authenticating with GCP using service account key..."
export GOOGLE_APPLICATION_CREDENTIALS="$(realpath "$SERVICE_ACCOUNT_KEY")"

# Check if jq is installed
if ! command -v jq &> /dev/null; then
  echo "❌ Error: jq is not installed. Please install it to continue."
  echo "   On Debian/Ubuntu: apt-get install jq"
  echo "   On macOS: brew install jq"
  exit 1
fi

# Extract service account email from the key file
SERVICE_ACCOUNT_EMAIL=$(cat "$SERVICE_ACCOUNT_KEY" | jq -r '.client_email')
if [[ -z "$SERVICE_ACCOUNT_EMAIL" || "$SERVICE_ACCOUNT_EMAIL" == "null" ]]; then
  echo "❌ Error: Could not extract service account email from key file."
  echo "   Please check that the key file is valid."
  exit 1
fi
echo "🔐 Using service account: $SERVICE_ACCOUNT_EMAIL"

# Force unlock if requested
if [[ -n "$FORCE_UNLOCK" ]]; then
  echo "🔓 Force unlocking state with lock ID: $FORCE_UNLOCK"
  terraform force-unlock -force "$FORCE_UNLOCK"
  echo "✅ State unlocked successfully"
  
  # If only unlocking was requested, exit here
  if [[ "$INIT_ONLY" != true && "$PLAN_ONLY" != true ]]; then
    exit 0
  fi
fi

# Initialize Terraform
echo "🔧 Initializing Terraform in $ENV_PATH..."
terraform init

if [[ "$INIT_ONLY" == true ]]; then
  echo "✅ Terraform initialization completed"
  exit 0
fi

# Automatically import existing service accounts
echo "🔄 Checking and importing existing service accounts..."
import_service_accounts

# Generate terraform.tfvars from example and environment variables
echo "📝 Checking for terraform.tfvars in $ENV_PATH..."

# Check if terraform.tfvars already exists
if [[ -f "terraform.tfvars" ]]; then
  echo "✅ Found existing terraform.tfvars file. Using it instead of generating a new one."
  
  # Ensure terraform_service_account is set in tfvars
  if ! grep -q "terraform_service_account" "terraform.tfvars"; then
    echo "⚠️ terraform_service_account not found in terraform.tfvars, adding it..."
    echo "terraform_service_account = \"$SERVICE_ACCOUNT_EMAIL\"" >> "terraform.tfvars"
  fi
  
  # Update deployment_stage in tfvars
  if grep -q "deployment_stage" "terraform.tfvars"; then
    sed -i.bak "s/deployment_stage = \".*\"/deployment_stage = \"$STAGE\"/" "terraform.tfvars" && rm -f "terraform.tfvars.bak"
    echo "✅ Updated deployment_stage in terraform.tfvars"
  else
    echo "deployment_stage = \"$STAGE\"" >> "terraform.tfvars"
    echo "✅ Added deployment_stage to terraform.tfvars"
  fi
  
  # Update create_sql_users in tfvars
  CREATE_SQL_USERS="true"
  if [[ "$STAGE" == "project" ]]; then
    CREATE_SQL_USERS="false"
  fi
  
  if grep -q "create_sql_users" "terraform.tfvars"; then
    sed -i.bak "s/create_sql_users = .*/create_sql_users = $CREATE_SQL_USERS/" "terraform.tfvars" && rm -f "terraform.tfvars.bak"
    echo "✅ Updated create_sql_users in terraform.tfvars to $CREATE_SQL_USERS"
  else
    echo "create_sql_users = $CREATE_SQL_USERS" >> "terraform.tfvars"
    echo "✅ Added create_sql_users to terraform.tfvars with value $CREATE_SQL_USERS"
  fi
else
  echo "📝 Generating terraform.tfvars for $ENV environment..."
  
  # Check if example file exists
  if [[ ! -f "terraform.tfvars.example" ]]; then
    echo "❌ terraform.tfvars.example not found in $ENV_PATH"
    exit 1
  fi

  # Create new terraform.tfvars file
  echo "# Auto-generated terraform.tfvars from environment variables" > "terraform.tfvars"

  # Look for common variables in GitHub Actions environment
  REGION=${TF_VAR_REGION:-}
  BILLING_ACCOUNT=${TF_VAR_BILLING_ACCOUNT:-}
  ORG_ID=${TF_VAR_ORG_ID:-}

  # Add common settings if they exist in environment variables
  if [[ -n "$REGION" ]]; then
    echo "region = \"$REGION\"" >> "terraform.tfvars"
    echo "✅ Using environment variable for region"
  fi

  if [[ -n "$BILLING_ACCOUNT" ]]; then
    echo "billing_account = \"$BILLING_ACCOUNT\"" >> "terraform.tfvars"
    echo "✅ Using environment variable for billing_account"
  fi

  if [[ -n "$ORG_ID" ]]; then
    echo "org_id = \"$ORG_ID\"" >> "terraform.tfvars"
    echo "✅ Using environment variable for org_id"
  fi
  
  # Always add the terraform_service_account
  echo "terraform_service_account = \"$SERVICE_ACCOUNT_EMAIL\"" >> "terraform.tfvars"
  echo "✅ Added terraform_service_account to terraform.tfvars"
  
  # Add deployment stage settings
  echo "deployment_stage = \"$STAGE\"" >> "terraform.tfvars"
  echo "✅ Added deployment_stage to terraform.tfvars"
  
  # Add create_sql_users setting
  CREATE_SQL_USERS="true"
  if [[ "$STAGE" == "project" ]]; then
    CREATE_SQL_USERS="false"
  fi
  echo "create_sql_users = $CREATE_SQL_USERS" >> "terraform.tfvars"
  echo "✅ Added create_sql_users to terraform.tfvars with value $CREATE_SQL_USERS"

  # Parse the example file to get all required variables
  echo "🔍 Extracting variables from example file..."
  REQUIRED_VARS=$(grep -v "^#" "terraform.tfvars.example" | grep "=" | cut -d "=" -f1 | tr -d " ")

  # Process each variable
  for VAR in $REQUIRED_VARS; do
    # Skip variables we've already processed
    if [[ "$VAR" == "region" || "$VAR" == "billing_account" || "$VAR" == "org_id" || "$VAR" == "terraform_service_account" || "$VAR" == "deployment_stage" || "$VAR" == "create_sql_users" ]]; then
      continue
    fi
    
    # Convert variable name to environment variable format
    ENV_VAR_NAME="TF_VAR_$(echo "$VAR" | tr '[:lower:]' '[:upper:]')"
    
    # Special logging for image variables
    if [[ "$VAR" == *"_image" ]]; then
      echo "🔍 Processing image variable: $VAR (env var: $ENV_VAR_NAME, value: ${!ENV_VAR_NAME})"
    fi
    
    # Check if environment variable exists
    if [[ -n "${!ENV_VAR_NAME}" ]]; then
      # Check if it's a boolean or number
      if [[ "${!ENV_VAR_NAME}" == "true" || "${!ENV_VAR_NAME}" == "false" || "${!ENV_VAR_NAME}" =~ ^[0-9]+$ ]]; then
        echo "$VAR = ${!ENV_VAR_NAME}" >> "terraform.tfvars"
      else
        # It's a string, add quotes
        echo "$VAR = \"${!ENV_VAR_NAME}\"" >> "terraform.tfvars"
      fi
      echo "✅ Using environment variable for $VAR"
      
      # Additional logging for image variables
      if [[ "$VAR" == *"_image" ]]; then
        echo "   Image value: ${!ENV_VAR_NAME}"
      fi
    else
      # For image variables, explicitly set empty string if not found
      if [[ "$VAR" == *"_image" ]]; then
        echo "$VAR = \"\"" >> "terraform.tfvars"
        echo "ℹ️ Setting empty value for $VAR to trigger default image"
      else
        # Get value from example file
        VAR_VALUE=$(grep "^$VAR[[:space:]]*=" "terraform.tfvars.example" | cut -d "=" -f2- | sed 's/^[[:space:]]*//')
        
        # Special handling for domains based on environment
        if [[ "$VAR" == *"_domain" ]]; then
          if [[ "$ENV" == "prd" ]]; then
            # Production uses clean domains
            case "$VAR" in
              backend_domain)
                VAR_VALUE=" \"api.rhesis.ai\""
                ;;
              frontend_domain)
                VAR_VALUE=" \"app.rhesis.ai\""
                ;;
              worker_domain)
                VAR_VALUE=" \"\""
                ;;
              polyphemus_domain)
                VAR_VALUE=" \"llm.rhesis.ai\""
                ;;
              chatbot_domain)
                VAR_VALUE=" \"chat.rhesis.ai\""
                ;;
            esac
          else
            # Non-production environments use env-prefixed domains
            case "$VAR" in
              backend_domain)
                VAR_VALUE=" \"$ENV-api.rhesis.ai\""
                ;;
              frontend_domain)
                VAR_VALUE=" \"$ENV-app.rhesis.ai\""
                ;;
              worker_domain)
                VAR_VALUE=" \"\""
                ;;
              polyphemus_domain)
                VAR_VALUE=" \"$ENV-llm.rhesis.ai\""
                ;;
              chatbot_domain)
                VAR_VALUE=" \"$ENV-chat.rhesis.ai\""
                ;;
            esac
          fi
        fi
        
        # Handle service_defaults, service_roles, and common_labels specially
        if [[ "$VAR" == "service_defaults" || "$VAR" == "service_roles" || "$VAR" == "common_labels" ]]; then
          echo "$VAR = {}" >> "terraform.tfvars"
          echo "⚠️ Using empty map for $VAR (will be loaded from common/defaults.tfvars)"
        else
          echo "$VAR =$VAR_VALUE" >> "terraform.tfvars"
          echo "ℹ️ Using example value for $VAR"
        fi
      fi
    fi
  done

  echo "✅ Generated terraform.tfvars file in $ENV_PATH"
fi

# Validate the configuration
echo "🔍 Validating Terraform configuration..."
terraform validate

# Define the plan file name
PLAN_FILE="terraform-${ENV}-plan"

# Apply common defaults and generate plan
echo "📋 Generating Terraform plan with common defaults from ../../common/defaults.tfvars..."
# Add -lock-timeout=60s to increase the chance of acquiring the lock
terraform plan -lock-timeout=60s -var-file=../../common/defaults.tfvars -var="terraform_service_account=$SERVICE_ACCOUNT_EMAIL" -var="deployment_stage=$STAGE" -var="create_sql_users=$CREATE_SQL_USERS" -out="$PLAN_FILE"
echo "✅ Plan generated and saved to $PLAN_FILE"

if [[ "$PLAN_ONLY" == true ]]; then
  echo "✅ Terraform plan phase completed successfully"
  exit 0
fi

# Apply the plan
echo "🚀 Applying Terraform plan..."

# Define variables for staged deployment
PROJECT_TARGET="-target=module.project"
# Add explicit exclusion for SQL user when using project stage
SQL_USER_EXCLUDE="-target=module.dev_environment.module.database.google_sql_user.user"
SERVICES_EXCLUDE="-target=module.project -target=module.project.google_project.project -target=module.project.google_project_service.project_services -target=module.project.time_sleep.wait_for_iam_propagation -target=module.project.google_project_iam_member.terraform_project_owner -target=module.project.google_project_iam_member.terraform_cloud_run_admin -target=module.project.google_project_iam_member.terraform_service_account_user -target=module.project.google_project_iam_member.terraform_artifact_registry_admin -target=module.project.google_project_iam_member.terraform_cloudsql_admin -target=module.project.google_project_iam_member.terraform_service_usage_admin -target=module.project.google_project_iam_member.terraform_project_iam_admin"

# Always ensure terraform_service_account is set during apply
TF_SERVICE_ACCOUNT_VAR="-var=terraform_service_account=$SERVICE_ACCOUNT_EMAIL"
TF_DEPLOYMENT_STAGE_VAR="-var=deployment_stage=$STAGE"
TF_CREATE_SQL_USERS_VAR="-var=create_sql_users=$CREATE_SQL_USERS"

if [[ "$STAGE" == "project" ]]; then
  echo "🏗️ Deploying project infrastructure only..."
  if [[ "$PLAN_ONLY" == true ]]; then
    # For plan only, use -target to exclude the SQL user resource
    echo "📋 Generating plan with explicit exclusion of SQL user resource..."
    terraform plan -lock-timeout=60s -var-file=../../common/defaults.tfvars $TF_SERVICE_ACCOUNT_VAR $TF_DEPLOYMENT_STAGE_VAR $TF_CREATE_SQL_USERS_VAR -target=module.dev_environment.module.database.google_sql_database_instance.instance -target=module.dev_environment.module.database.google_sql_database.database "$PROJECT_TARGET" -out="$PLAN_FILE"
  elif [[ "$AUTO_APPROVE" == true ]]; then
    terraform apply -lock-timeout=60s -auto-approve $TF_SERVICE_ACCOUNT_VAR $TF_DEPLOYMENT_STAGE_VAR $TF_CREATE_SQL_USERS_VAR "$PROJECT_TARGET" "$PLAN_FILE"
  else
    terraform apply -lock-timeout=60s $TF_SERVICE_ACCOUNT_VAR $TF_DEPLOYMENT_STAGE_VAR $TF_CREATE_SQL_USERS_VAR "$PROJECT_TARGET" "$PLAN_FILE"
  fi
  echo "✅ Project infrastructure deployment completed successfully!"
  echo "⚠️ To deploy services, run this script again with --stage services"
  
elif [[ "$STAGE" == "services" ]]; then
  echo "🏗️ Deploying services only (assuming project already exists)..."
  if [[ "$AUTO_APPROVE" == true ]]; then
    terraform apply -lock-timeout=60s -auto-approve $TF_SERVICE_ACCOUNT_VAR $TF_DEPLOYMENT_STAGE_VAR $TF_CREATE_SQL_USERS_VAR "$PLAN_FILE"
  else
    terraform apply -lock-timeout=60s $TF_SERVICE_ACCOUNT_VAR $TF_DEPLOYMENT_STAGE_VAR $TF_CREATE_SQL_USERS_VAR "$PLAN_FILE"
  fi
  echo "✅ Services deployment completed successfully!"
  
else # all
  echo "🏗️ Deploying complete infrastructure (project and services)..."
  echo "⚠️ For more reliable deployment, consider using --stage project followed by --stage services"
  
  if [[ "$AUTO_APPROVE" == true ]]; then
    # First deploy the project
    echo "🏗️ Step 1/2: Deploying project infrastructure..."
    terraform apply -lock-timeout=60s -auto-approve $TF_SERVICE_ACCOUNT_VAR $TF_DEPLOYMENT_STAGE_VAR "-var=create_sql_users=false" "$PROJECT_TARGET" "$PLAN_FILE"
    
    # Wait for APIs and permissions to fully propagate
    echo "⏳ Waiting for 3 minutes to ensure APIs and permissions are fully propagated..."
    sleep 180
    
    # Then deploy the services
    echo "🏗️ Step 2/2: Deploying services..."
    terraform apply -lock-timeout=60s -auto-approve $TF_SERVICE_ACCOUNT_VAR $TF_DEPLOYMENT_STAGE_VAR "-var=create_sql_users=true" "$PLAN_FILE"
  else
    # First deploy the project
    echo "🏗️ Step 1/2: Deploying project infrastructure..."
    terraform apply -lock-timeout=60s $TF_SERVICE_ACCOUNT_VAR $TF_DEPLOYMENT_STAGE_VAR "-var=create_sql_users=false" "$PROJECT_TARGET" "$PLAN_FILE"
    
    # Wait for APIs and permissions to fully propagate
    echo "⏳ Waiting for 3 minutes to ensure APIs and permissions are fully propagated..."
    sleep 180
    
    # Then deploy the services
    echo "🏗️ Step 2/2: Deploying services..."
    terraform apply -lock-timeout=60s $TF_SERVICE_ACCOUNT_VAR $TF_DEPLOYMENT_STAGE_VAR "-var=create_sql_users=true" "$PLAN_FILE"
  fi
fi

echo "✅ Deployment to $ENV environment completed successfully!" 