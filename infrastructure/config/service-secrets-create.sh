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
  echo "Set up GitHub secrets for service deployment"
  echo ""
  echo -e "${BLUE}Options:${NC}"
  echo "  -r, --repo REPO         GitHub repository in format 'owner/repo'"
  echo "  -e, --environments      Comma-separated list of environments to set up [default: dev,stg,prd]"
  echo "  -h, --help              Show this help message"
  echo ""
  echo -e "${BLUE}Environment-specific Variables (set for each environment):${NC}"
  echo "  # Backend variables"
  echo "  SQLALCHEMY_DATABASE_URL       Full database URL"
  echo "  SQLALCHEMY_DB_MODE            Database mode"
  echo "  SQLALCHEMY_DB_DRIVER          Database driver"
  echo "  SQLALCHEMY_DB_USER            Database user"
  echo "  SQLALCHEMY_DB_PASS            Database password"
  echo "  SQLALCHEMY_DB_HOST            Database host"
  echo "  SQLALCHEMY_DB_NAME            Database name"
  echo "  LOG_LEVEL                     Logging level"
  echo "  AUTH0_DOMAIN                  Auth0 domain"
  echo "  AUTH0_AUDIENCE                Auth0 audience"
  echo "  AUTH0_CLIENT_ID               Auth0 client ID"
  echo "  AUTH0_CLIENT_SECRET           Auth0 client secret"
  echo "  AUTH0_SECRET_KEY              Auth0 secret key"
  echo "  JWT_SECRET_KEY                JWT secret key"
  echo "  JWT_ALGORITHM                 JWT algorithm"
  echo "  JWT_ACCESS_TOKEN_EXPIRE_MINUTES JWT token expiration"
  echo "  FRONTEND_URL                  Frontend URL"
  echo "  AZURE_OPENAI_ENDPOINT         Azure OpenAI endpoint"
  echo "  AZURE_OPENAI_API_KEY          Azure OpenAI API key"
  echo "  AZURE_OPENAI_DEPLOYMENT_NAME  Azure OpenAI deployment name"
  echo "  AZURE_OPENAI_API_VERSION      Azure OpenAI API version"
  echo "  GEMINI_API_KEY                Google Gemini API key"
  echo "  GEMINI_MODEL_NAME             Google Gemini model name"
  echo "  RHESIS_BASE_URL               Rhesis base URL"
  echo "  SMTP_HOST                     SMTP host"
  echo "  SMTP_PORT                     SMTP port"
  echo "  SMTP_USER                     SMTP user"
  echo "  SMTP_PASSWORD                 SMTP password"
  echo ""
  echo "  # Celery worker variables"
  echo "  BROKER_URL                    Celery broker URL"
  echo "  CELERY_RESULT_BACKEND         Celery result backend URL"
  echo "  CELERY_WORKER_CONCURRENCY     Worker concurrency (number of processes)"
  echo "  CELERY_WORKER_PREFETCH_MULTIPLIER Worker prefetch multiplier"
  echo "  CELERY_WORKER_MAX_TASKS_PER_CHILD Max tasks per child process"
  echo ""
  echo "  # Frontend variables"
  echo "  NEXTAUTH_URL                  NextAuth URL"
  echo "  NEXTAUTH_SECRET               NextAuth secret"
  echo "  NEXT_PUBLIC_API_BASE_URL      API base URL for frontend"
  echo "  AUTH_SECRET                   Authentication secret"
  echo "  GOOGLE_CLIENT_ID              Google OAuth client ID"
  echo "  GOOGLE_CLIENT_SECRET          Google OAuth client secret"
  echo "  NEXT_PUBLIC_APP_URL           Public app URL"
  echo "  NEXT_PUBLIC_AUTH0_CLIENT_ID   Auth0 client ID for frontend"
  echo "  NEXT_PUBLIC_AUTH0_DOMAIN      Auth0 domain for frontend"
  echo "  DATABASE_URL                  Database URL for frontend"
  echo ""
  echo -e "${BLUE}Example:${NC}"
  echo "  $0 --repo myuser/myrepo"
}

# Default values
REPO=""
ENVIRONMENTS="dev,stg,prd"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    -r|--repo)
      REPO="$2"
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

# Service environment variables
SERVICE_VARS=(
  # Backend variables
  "SQLALCHEMY_DATABASE_URL"
  "SQLALCHEMY_DB_MODE"
  "SQLALCHEMY_DB_DRIVER"
  "SQLALCHEMY_DB_USER"
  "SQLALCHEMY_DB_PASS"
  "SQLALCHEMY_DB_HOST"
  "SQLALCHEMY_DB_NAME"
  "LOG_LEVEL"
  "AUTH0_DOMAIN"
  "AUTH0_AUDIENCE"
  "AUTH0_CLIENT_ID"
  "AUTH0_CLIENT_SECRET"
  "AUTH0_SECRET_KEY"
  "JWT_SECRET_KEY"
  "JWT_ALGORITHM"
  "JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
  "FRONTEND_URL"
  "AZURE_OPENAI_ENDPOINT"
  "AZURE_OPENAI_API_KEY"
  "AZURE_OPENAI_DEPLOYMENT_NAME"
  "AZURE_OPENAI_API_VERSION"
  "GEMINI_API_KEY"
  "GEMINI_MODEL_NAME"
  "RHESIS_BASE_URL"
  "SMTP_HOST"
  "SMTP_PORT"
  "SMTP_USER"
  "SMTP_PASSWORD"
  
  # Celery worker variables
  "BROKER_URL"
  "CELERY_RESULT_BACKEND"
  "CELERY_WORKER_CONCURRENCY"
  "CELERY_WORKER_PREFETCH_MULTIPLIER"
  "CELERY_WORKER_MAX_TASKS_PER_CHILD"
  
  # Frontend variables
  "NEXTAUTH_URL"
  "NEXTAUTH_SECRET"
  "NEXT_PUBLIC_API_BASE_URL"
  "AUTH_SECRET"
  "GOOGLE_CLIENT_ID"
  "GOOGLE_CLIENT_SECRET"
  "NEXT_PUBLIC_APP_URL"
  "NEXT_PUBLIC_AUTH0_CLIENT_ID"
  "NEXT_PUBLIC_AUTH0_DOMAIN"
  "DATABASE_URL"
)

# Set environment-specific secrets
for env in "${ENV_ARRAY[@]}"; do
  env_upper=$(echo "$env" | tr '[:lower:]' '[:upper:]')
  echo -e "${BLUE}Setting up secrets for $env environment...${NC}"
  
  # Set all service environment variables
  for var_name in "${SERVICE_VARS[@]}"; do
    env_var="${env_upper}_${var_name}"
    
    if [[ -n "${!env_var}" ]]; then
      set_secret "$env" "$var_name" "${!env_var}"
    else
      echo -e "${YELLOW}Warning:${NC} $env_var environment variable is not set"
    fi
  done
  
  # Set default frontend URLs if not provided
  if [[ -z "${!env_upper}_FRONTEND_URL" ]]; then
    if [[ "$env" == "prd" ]]; then
      frontend_url="https://app.rhesis.ai"
    else
      frontend_url="https://$env-app.rhesis.ai"
    fi
    echo -e "${YELLOW}Warning:${NC} ${env_upper}_FRONTEND_URL not set, using default: $frontend_url"
    set_secret "$env" "FRONTEND_URL" "$frontend_url"
  fi
  
  # Set default NextAuth URL if not provided
  if [[ -z "${!env_upper}_NEXTAUTH_URL" ]]; then
    if [[ "$env" == "prd" ]]; then
      nextauth_url="https://app.rhesis.ai"
    else
      nextauth_url="https://$env-app.rhesis.ai"
    fi
    echo -e "${YELLOW}Warning:${NC} ${env_upper}_NEXTAUTH_URL not set, using default: $nextauth_url"
    set_secret "$env" "NEXTAUTH_URL" "$nextauth_url"
  fi
  
  # Set default API URL if not provided
  if [[ -z "${!env_upper}_NEXT_PUBLIC_API_BASE_URL" ]]; then
    if [[ "$env" == "prd" ]]; then
      api_url="https://api.rhesis.ai"
    else
      api_url="https://$env-api.rhesis.ai"
    fi
    echo -e "${YELLOW}Warning:${NC} ${env_upper}_NEXT_PUBLIC_API_BASE_URL not set, using default: $api_url"
    set_secret "$env" "NEXT_PUBLIC_API_BASE_URL" "$api_url"
  fi
  
  # Set default APP URL if not provided
  if [[ -z "${!env_upper}_NEXT_PUBLIC_APP_URL" ]]; then
    if [[ "$env" == "prd" ]]; then
      app_url="https://app.rhesis.ai"
    else
      app_url="https://$env-app.rhesis.ai"
    fi
    echo -e "${YELLOW}Warning:${NC} ${env_upper}_NEXT_PUBLIC_APP_URL not set, using default: $app_url"
    set_secret "$env" "NEXT_PUBLIC_APP_URL" "$app_url"
  fi
  
  # Set default log level if not provided
  if [[ -z "${!env_upper}_LOG_LEVEL" ]]; then
    if [[ "$env" == "prd" ]]; then
      log_level="INFO"
    else
      log_level="DEBUG"
    fi
    echo -e "${YELLOW}Warning:${NC} ${env_upper}_LOG_LEVEL not set, using default: $log_level"
    set_secret "$env" "LOG_LEVEL" "$log_level"
  fi
done

echo -e "${GREEN}✅ GitHub secrets setup completed successfully!${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. Go to GitHub repository settings to review the secrets"
echo "2. Run the service CI/CD workflows from the Actions tab"
echo "3. Select the environment you want to deploy" 