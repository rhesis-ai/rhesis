#!/bin/bash
# Optimized Deployment script for Rhesis Polyphemus LLM service

# Exit immediately if a command exits with a non-zero status
set -e

# Set variables
PROJECT_ID="playground-437609"  # Replace with your GCP project ID
SERVICE_NAME="rhesis-polyphemus"
REGION="us-central1"  # Make sure this region supports GPUs on Cloud Run
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

# Optional: If you need a Hugging Face token for private models
# export HF_TOKEN="your_huggingface_token"

# Build the container image with cache using cloudbuild.yaml
echo "Building container image with caching..."
gcloud builds submit \
  --config="cloudbuild.yaml" \
  --substitutions="_IMAGE_NAME=${IMAGE_NAME}" .

# Deploy to Cloud Run with GPU
echo "Deploying to Cloud Run with GPU..."
gcloud beta run deploy ${SERVICE_NAME} \
  --image=${IMAGE_NAME} \
  --platform=managed \
  --region=${REGION} \
  --gpu=1 \
  --gpu-type=nvidia-l4 \
  --memory=16Gi \
  --cpu=4 \
  --timeout=3600 \
  --min-instances=1 \
  --max-instances=1 \
  --port=8080 \
  --concurrency=1 \
  --allow-unauthenticated \
  --set-env-vars="HF_MODEL=cognitivecomputations/Dolphin3.0-Llama3.1-8B" \
  --no-cpu-throttling \
  --service-account="${SERVICE_NAME}-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Create a specific service account if you don't have one yet
# Uncomment if needed:
# gcloud iam service-accounts create ${SERVICE_NAME}-sa \
#   --display-name="Service Account for ${SERVICE_NAME}"

# Optional: Set up monitoring alerts for high latency
echo "Setting up monitoring alert policy..."
gcloud alpha monitoring policies create \
  --condition-filter="resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${SERVICE_NAME}\" AND metric.type=\"run.googleapis.com/request_latencies\" AND metric.labels.response_code=\"200\" AND metric.labels.response_code_class=\"2xx\" AND metric.labels.quantile=\"50\"" \
  --condition-threshold-value=10000 \
  --condition-threshold-duration=300s \
  --condition-aggregations-per-series-aligner=ALIGN_PERCENTILE_50 \
  --condition-aggregations-alignment-period=60s \
  --condition-trigger-count=1 \
  --condition-display-name="High Latency Alert for ${SERVICE_NAME}" \
  --display-name="${SERVICE_NAME} Latency Alert" \
  --documentation-content="The ${SERVICE_NAME} model is experiencing high latency. Consider scaling up resources or optimizing the model."

# Create a scheduled job to warm up the model after deployments
# This helps reduce cold start times for users
echo "Creating warm-up job..."
gcloud scheduler jobs create http ${SERVICE_NAME}-warmup \
  --schedule="*/30 * * * *" \
  --uri="$(gcloud run services describe ${SERVICE_NAME} --region=${REGION} --format='value(status.url)')/health" \
  --http-method=GET \
  --oidc-service-account-email="${SERVICE_NAME}-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --oidc-token-audience="$(gcloud run services describe ${SERVICE_NAME} --region=${REGION} --format='value(status.url)')"

echo "Deployment complete! The service URL is:"
gcloud run services describe ${SERVICE_NAME} \
  --region=${REGION} \
  --format="value(status.url)"

echo ""
echo "Test your deployment with:"
echo "curl -X POST $(gcloud run services describe ${SERVICE_NAME} --region=${REGION} --format='value(status.url)')/generate \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"prompt\": \"What is artificial intelligence?\", \"max_tokens\": 100}'"