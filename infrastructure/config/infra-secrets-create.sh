#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to display usage information
function show_usage() {
  echo -e "${BLUE}Usage:${NC} $0 [OPTIONS]"
  echo "Set up GitHub secrets for Terraform deployment"
  echo ""
  echo -e "${BLUE}Options:${NC}"
  echo "  -r, --repo REPO         GitHub repository in format 'owner/repo'"
  echo "  -k, --key FILE          Path to GCP service account key JSON file [default: terraform-deployer-key.json]"
  echo "  -e, --environments      Comma-separated list of environments to set up [default: dev,stg,prd]"
  echo "  -h, --help              Show this help message"
  echo ""
  echo -e "${BLUE}Required Environment Variables:${NC}"
  echo "  REGION                  GCP region (e.g., europe-west4)"
  echo "  BILLING_ACCOUNT         GCP billing account ID"
  echo "  ORG_ID                  GCP organization ID"
  echo ""
  echo -e "${BLUE}Environment-specific Variables (set for each environment):${NC}"
  echo "  DATABASE_PASSWORD       Database password"
  echo "  BACKEND_IMAGE           Backend container image URL"
  echo "  FRONTEND_IMAGE          Frontend container image URL"
  echo "  WORKER_IMAGE            Worker container image URL"
  echo "  POLYPHEMUS_IMAGE        Polyphemus container image URL"
  echo "  CHATBOT_IMAGE           Chatbot container image URL"
  echo "  ENABLE_LOAD_BALANCERS   Whether to enable load balancers (true/false)"
  echo ""
  echo -e "${BLUE}Example:${NC}"
  echo "  $0 --repo myuser/myrepo"
}

# Default values
REPO=""
KEY_FILE="terraform-deployer-key.json"
ENVIRONMENTS="dev,stg,prd"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    -r|--repo)
      REPO="$2"
      shift 2
      ;;
    -k|--key)
      KEY_FILE="$2"
      shift 2
      ;;
    -e|--environments)
      ENVIRONMENTS="$2"
      shift 2
      ;;
    -h|--help)
      show_usage
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option:${NC} $1"
      show_usage
      exit 1
      ;;
  esac
done

# Check for required repository
if [[ -z "$REPO" ]]; then
  echo -e "${RED}Error:${NC} GitHub repository is required"
  show_usage
  exit 1
fi

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
  echo -e "${RED}Error:${NC} GitHub CLI (gh) is not installed. Please install it first:"
  echo "https://cli.github.com/manual/installation"
  exit 1
fi

# Check if user is authenticated with GitHub CLI
if ! gh auth status &> /dev/null; then
  echo -e "${RED}Error:${NC} Not authenticated with GitHub CLI. Please run 'gh auth login' first."
  exit 1
fi

# Check if the repository exists and is accessible
if ! gh repo view "$REPO" &> /dev/null; then
  echo -e "${RED}Error:${NC} Repository '$REPO' does not exist or is not accessible."
  exit 1
fi

# Check for required service account key
if [[ ! -f "$KEY_FILE" ]]; then
  echo -e "${RED}Error:${NC} Service account key file not found: $KEY_FILE"
  exit 1
fi

# Check for required environment variables
if [[ -z "$REGION" ]]; then
  echo -e "${YELLOW}Warning:${NC} REGION environment variable is not set. Using default: europe-west4"
  REGION="europe-west4"
fi

if [[ -z "$BILLING_ACCOUNT" ]]; then
  echo -e "${RED}Error:${NC} BILLING_ACCOUNT environment variable is required"
  exit 1
fi

if [[ -z "$ORG_ID" ]]; then
  echo -e "${RED}Error:${NC} ORG_ID environment variable is required"
  exit 1
fi

# Convert environments string to array
IFS=',' read -ra ENV_ARRAY <<< "$ENVIRONMENTS"

# Function to set a secret for a specific environment
function set_secret() {
  local env=$1
  local secret_name=$2
  local secret_value=$3
  
  # Check if environment exists, create if not
  if ! gh api "repos/$REPO/environments/$env" &> /dev/null; then
    echo -e "${YELLOW}Environment '$env' does not exist. Creating...${NC}"
    gh api -X PUT "repos/$REPO/environments/$env" --silent
  fi
  
  echo -e "${GREEN}Setting secret:${NC} $secret_name for environment: $env"
  echo "$secret_value" | gh secret set "$secret_name" --repo "$REPO" --env "$env"
}

# Function to set a repository-level secret
function set_repo_secret() {
  local secret_name=$1
  local secret_value=$2
  
  echo -e "${GREEN}Setting repository secret:${NC} $secret_name"
  echo "$secret_value" | gh secret set "$secret_name" --repo "$REPO"
}

# Set common secrets at repository level
echo -e "${BLUE}Setting common repository secrets...${NC}"
set_repo_secret "TF_VAR_REGION" "$REGION"
set_repo_secret "TF_VAR_BILLING_ACCOUNT" "$BILLING_ACCOUNT"
set_repo_secret "TF_VAR_ORG_ID" "$ORG_ID"

# Set GCP service account key as repository secret
echo -e "${BLUE}Setting GCP service account key...${NC}"
cat "$KEY_FILE" | gh secret set "GCP_SA_KEY" --repo "$REPO"

# Set environment-specific secrets
for env in "${ENV_ARRAY[@]}"; do
  env_upper=$(echo "$env" | tr '[:lower:]' '[:upper:]')
  echo -e "${BLUE}Setting up secrets for $env environment...${NC}"
  
  # Database password
  db_password_var="${env_upper}_DATABASE_PASSWORD"
  if [[ -n "${!db_password_var}" ]]; then
    set_secret "$env" "TF_VAR_DATABASE_PASSWORD" "${!db_password_var}"
  else
    echo -e "${YELLOW}Warning:${NC} $db_password_var environment variable is not set"
  fi
  
  # Container images
  for service in BACKEND FRONTEND WORKER POLYPHEMUS CHATBOT; do
    image_var="${env_upper}_${service}_IMAGE"
    if [[ -n "${!image_var}" ]]; then
      set_secret "$env" "TF_VAR_${service}_IMAGE" "${!image_var}"
    else
      echo -e "${YELLOW}Warning:${NC} $image_var environment variable is not set"
    fi
  done
  
  # Load balancer settings
  lb_var="${env_upper}_ENABLE_LOAD_BALANCERS"
  if [[ -n "${!lb_var}" ]]; then
    set_secret "$env" "TF_VAR_ENABLE_LOAD_BALANCERS" "${!lb_var}"
  else
    echo -e "${YELLOW}Warning:${NC} $lb_var environment variable is not set, using default: true"
    set_secret "$env" "TF_VAR_ENABLE_LOAD_BALANCERS" "true"
  fi
  
  # Domain settings
  # For production, use clean domains
  if [[ "$env" == "prd" ]]; then
    domains=(
      "BACKEND_DOMAIN:api.rhesis.ai"
      "FRONTEND_DOMAIN:app.rhesis.ai"
      "WORKER_DOMAIN:"
      "POLYPHEMUS_DOMAIN:llm.rhesis.ai"
      "CHATBOT_DOMAIN:chat.rhesis.ai"
    )
  else
    # For non-production, use env-prefixed domains
    domains=(
      "BACKEND_DOMAIN:$env-api.rhesis.ai"
      "FRONTEND_DOMAIN:$env-app.rhesis.ai"
      "WORKER_DOMAIN:"
      "POLYPHEMUS_DOMAIN:$env-llm.rhesis.ai"
      "CHATBOT_DOMAIN:$env-chat.rhesis.ai"
    )
  fi
  
  for domain_pair in "${domains[@]}"; do
    IFS=':' read -r domain_key domain_default <<< "$domain_pair"
    domain_var="${env_upper}_${domain_key}"
    
    if [[ -n "${!domain_var}" ]]; then
      set_secret "$env" "TF_VAR_${domain_key}" "${!domain_var}"
    elif [[ -n "$domain_default" ]]; then
      echo -e "${YELLOW}Warning:${NC} $domain_var environment variable is not set, using default: $domain_default"
      set_secret "$env" "TF_VAR_${domain_key}" "$domain_default"
    fi
  done
done

echo -e "${GREEN}✅ GitHub secrets setup completed successfully!${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. Go to GitHub repository settings to review the secrets"
echo "2. Run the Infrastructure workflow from the Actions tab"
echo "3. Select the environment you want to deploy" 