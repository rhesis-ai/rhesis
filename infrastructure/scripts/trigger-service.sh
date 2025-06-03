#!/bin/bash
set -e

# Function to display usage information
function show_usage() {
  echo "Usage: $0 [OPTIONS]"
  echo "Trigger GitHub Actions workflow for backend or frontend service"
  echo ""
  echo "Options:"
  echo "  -s, --service SERVICE    Service to deploy (backend, frontend) [required]"
  echo "  -e, --environment ENV    Environment to deploy (dev, stg, prd) [default: dev]"
  echo "  -b, --branch BRANCH      Specify the branch containing the workflow [default: current branch]"
  echo "  -w, --workflow FILE      Specify the workflow file path [default: <service>.yml]"
  echo "  -h, --help               Show this help message"
  echo ""
  echo "Example:"
  echo "  $0 --service backend --environment stg"
  echo "  $0 --service frontend --environment prd --branch main"
  echo "  $0 --service backend --environment dev"
}

# Default values
ENVIRONMENT="dev"
# Branch is intentionally left empty to use current branch by default

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    -s|--service)
      SERVICE="$2"
      shift 2
      ;;
    -e|--environment)
      ENVIRONMENT="$2"
      shift 2
      ;;
    -b|--branch)
      BRANCH="$2"
      shift 2
      ;;
    -w|--workflow)
      WORKFLOW_FILE="$2"
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

# Validate service parameter
if [[ -z "$SERVICE" ]]; then
  echo "❌ Service parameter is required"
  show_usage
  exit 1
fi

# Convert service to lowercase for case-insensitive comparison
SERVICE=$(echo "$SERVICE" | tr '[:upper:]' '[:lower:]')

# Validate service
if [[ "$SERVICE" != "backend" && "$SERVICE" != "frontend" ]]; then
  echo "❌ Invalid service: $SERVICE"
  echo "Valid services: backend, frontend"
  exit 1
fi

# Set workflow file if not specified
if [[ -z "$WORKFLOW_FILE" ]]; then
  WORKFLOW_FILE="${SERVICE}.yml"
fi

# Validate environment
if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "stg" && "$ENVIRONMENT" != "prd" ]]; then
  echo "❌ Invalid environment: $ENVIRONMENT"
  echo "Valid environments: dev, stg, prd"
  exit 1
fi

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
  echo "❌ GitHub CLI (gh) is not installed. Please install it first:"
  echo "https://cli.github.com/manual/installation"
  exit 1
fi

# Check if user is authenticated with GitHub CLI
if ! gh auth status &> /dev/null; then
  echo "❌ Not authenticated with GitHub CLI. Please run 'gh auth login' first."
  exit 1
fi

# Navigate to the project root directory to ensure we're in the git repository
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../.."

# If branch is not specified, use the current branch
if [[ -z "$BRANCH" ]]; then
  BRANCH=$(git rev-parse --abbrev-ref HEAD)
  echo "ℹ️ Using current branch: $BRANCH"
fi

# Get the default branch
DEFAULT_BRANCH=$(gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name' 2>/dev/null || echo "main")
echo "ℹ️ Default branch is: $DEFAULT_BRANCH"

# Check if the workflow file exists on the specified branch
if ! gh api "repos/:owner/:repo/contents/.github/workflows/$WORKFLOW_FILE?ref=$BRANCH" &> /dev/null; then
  echo "⚠️ Workflow file not found on branch '$BRANCH'"
  
  # Check if it exists on the default branch
  if gh api "repos/:owner/:repo/contents/.github/workflows/$WORKFLOW_FILE?ref=$DEFAULT_BRANCH" &> /dev/null; then
    echo "ℹ️ Workflow file found on default branch '$DEFAULT_BRANCH'"
    echo "ℹ️ Switching to default branch for workflow execution"
    BRANCH=$DEFAULT_BRANCH
  else
    echo "❌ Workflow file not found on default branch either."
    echo "   Please make sure the workflow file exists at .github/workflows/$WORKFLOW_FILE"
    exit 1
  fi
fi

# Format service name for display (capitalize first letter)
DISPLAY_SERVICE="${SERVICE^}"

# Trigger the workflow
echo "🚀 Triggering $DISPLAY_SERVICE workflow for $ENVIRONMENT environment..."
echo "   Branch: $BRANCH"
echo "   Workflow: $WORKFLOW_FILE"

# Run the workflow with the specified parameters
CMD="gh workflow run $WORKFLOW_FILE"
CMD="$CMD -f environment=$ENVIRONMENT"
CMD="$CMD --ref $BRANCH"

echo "ℹ️ Executing: $CMD"
eval "$CMD"

if [ $? -eq 0 ]; then
  echo "✅ Workflow triggered successfully!"
  echo "⏳ To view the workflow run, visit the Actions tab in your GitHub repository."
  echo "   You can run 'gh run list --workflow=$WORKFLOW_FILE' to see recent workflow runs."
else
  echo "❌ Failed to trigger workflow."
  echo "   Make sure the workflow file exists at .github/workflows/$WORKFLOW_FILE on branch: $BRANCH"
  echo "   Also ensure the workflow has the 'workflow_dispatch' trigger defined."
  echo ""
  echo "   If you're seeing a 422 error, it's likely that the workflow exists but doesn't have"
  echo "   the workflow_dispatch trigger or the workflow file hasn't been committed/pushed yet."
fi 