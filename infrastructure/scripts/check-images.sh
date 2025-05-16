#!/bin/bash
set -e

# ========================================================================
# Container Image Validation Script for Terraform Deployments
# ========================================================================
#
# Purpose:
# This script solves the "chicken and egg" problem in infrastructure deployment
# by validating container images before Terraform runs. It ensures that:
#
# 1. Infrastructure can be deployed even before container images exist
# 2. Only valid, existing images are used in the deployment
# 3. Services fallback to public images when custom images don't exist
#
# The script checks if specified container images exist in the GCP Artifact Registry.
# For images that exist, it maintains their values for Terraform.
# For images that don't exist, it sets empty values which cause Terraform 
# to use default public images via the coalesce() function.
#
# This approach prevents deployment failures due to non-existent images
# and enables infrastructure-first deployment strategies.
#
# ========================================================================

# Default values
PROJECT_ID=""
ENV="dev"
REGION="europe-west4"
SERVICES=("backend" "frontend" "worker" "polyphemus" "chatbot")

# Function to display usage information
function show_usage() {
  echo "Usage: $0 [OPTIONS]"
  echo "Check if container images exist and set environment variables for Terraform"
  echo ""
  echo "Options:"
  echo "  -p, --project PROJECT_ID   GCP project ID [required]"
  echo "  -e, --environment ENV      Environment (dev, stg, prd) [default: dev]"
  echo "  -r, --region REGION        GCP region [default: europe-west4]"
  echo "  -h, --help                 Show this help message"
  echo ""
  echo "Example:"
  echo "  $0 --project rhesis-dev --environment dev"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    -p|--project)
      PROJECT_ID="$2"
      shift 2
      ;;
    -e|--environment)
      ENV="$2"
      shift 2
      ;;
    -r|--region)
      # Check if the next argument is a valid region (not starting with a dash)
      if [[ -n "$2" ]] && [[ "$2" != -* ]]; then
        REGION="$2"
        shift 2
      else
        echo "⚠️ Warning: No region specified after --region flag, using default: ${REGION}"
        shift 1
      fi
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

# Check for required project ID
if [[ -z "$PROJECT_ID" ]]; then
  echo "❌ Error: GCP project ID is required"
  show_usage
  exit 1
fi

echo "🔍 Using region: $REGION"

# Map environment to short form
case "$ENV" in
  dev)
    ENV_SHORT="dev"
    ;;
  stg)
    ENV_SHORT="stg"
    ;;
  prd)
    ENV_SHORT="prd"
    ;;
  *)
    echo "❌ Error: Invalid environment: $ENV"
    echo "Valid environments: dev, stg, prd"
    exit 1
    ;;
esac

echo "🔍 Checking for existing container registry in project $PROJECT_ID..."

# Check if the artifact registry exists
REGISTRY_EXISTS=$(gcloud artifacts repositories list --project="$PROJECT_ID" --filter="name:${ENV}-container-registry" --format="value(name)" 2>/dev/null || echo "")

if [[ -z "$REGISTRY_EXISTS" ]]; then
  echo "⚠️ Artifact registry '${ENV}-container-registry' does not exist yet in project $PROJECT_ID"
  echo "ℹ️ This is expected for initial deployments. Default images will be used."
  
  # Create empty environment variables for all services
  for SERVICE in "${SERVICES[@]}"; do
    VAR_NAME="TF_VAR_$(echo "${SERVICE}_IMAGE" | tr '[:lower:]' '[:upper:]')"
    echo "$VAR_NAME=" >> $GITHUB_ENV
    echo "ℹ️ Set $VAR_NAME to empty (will use default image)"
  done
  
  exit 0
fi

echo "✅ Artifact registry '${ENV}-container-registry' exists in project $PROJECT_ID"
REGISTRY_HOST="$REGION-docker.pkg.dev/$PROJECT_ID/${ENV}-container-registry"

# Function to check if an image exists in the registry
function image_exists() {
  local image_name="$1"
  local image_tag="$2"
  
  # Try to get the image digest
  if gcloud artifacts docker images describe "$image_name:$image_tag" --quiet > /dev/null 2>&1; then
    return 0  # Image exists
  else
    return 1  # Image does not exist
  fi
}

for SERVICE in "${SERVICES[@]}"; do
  echo "📦 Checking service: $SERVICE"
  
  # Get the original image from environment
  ENV_VAR_NAME="TF_VAR_$(echo "${SERVICE}_IMAGE" | tr '[:lower:]' '[:upper:]')"
  ORIGINAL_IMAGE="${!ENV_VAR_NAME}"
  
  # Skip if not set
  if [[ -z "$ORIGINAL_IMAGE" ]]; then
    echo "⏭️ No image specified for $SERVICE, using default"
    echo "$ENV_VAR_NAME=" >> $GITHUB_ENV
    continue
  fi
  
  # For GCP Artifact Registry images, we'll check if they exist
  if [[ "$ORIGINAL_IMAGE" == *"$REGISTRY_HOST"* ]]; then
    IMAGE_TAG="latest"
    if [[ "$ORIGINAL_IMAGE" == *":"* ]]; then
      IMAGE_TAG=$(echo "$ORIGINAL_IMAGE" | cut -d':' -f2)
    fi
    
    IMAGE_PATH="$REGISTRY_HOST/$SERVICE"
    
    if image_exists "$IMAGE_PATH" "$IMAGE_TAG"; then
      echo "✅ Image exists: $ORIGINAL_IMAGE"
      echo "$ENV_VAR_NAME=$ORIGINAL_IMAGE" >> $GITHUB_ENV
    else
      echo "⚠️ Image does not exist: $ORIGINAL_IMAGE"
      echo "$ENV_VAR_NAME=" >> $GITHUB_ENV
      echo "ℹ️ Will use default image for $SERVICE"
    fi
  else
    # For external images (like Docker Hub), we'll assume they exist
    echo "ℹ️ Using external image: $ORIGINAL_IMAGE"
    echo "$ENV_VAR_NAME=$ORIGINAL_IMAGE" >> $GITHUB_ENV
  fi
done

echo "🎉 Image checking complete! Environment variables set for Terraform." 