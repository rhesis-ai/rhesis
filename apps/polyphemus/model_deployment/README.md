# Polyphemus Vertex AI Deployment

This directory contains scripts and configuration for deploying ML models to Google Cloud Vertex AI using vLLM (Very Large Language Models).

## Overview

The Vertex AI deployment capability allows you to:
- Deploy large language models to Vertex AI endpoints
- Use vLLM for optimized inference performance
- Configure GPU types and counts for your deployments
- Manage multiple model endpoints from a single configuration
- Integrate with existing Cloud Run deployments

**Note**: This deployment is **separate** from the existing Cloud Run deployment. You can use both:
- **Cloud Run**: For the Polyphemus API service (existing functionality)
- **Vertex AI**: For deploying ML models as managed endpoints (new functionality)

## Directory Structure

```
model_deployment/
├── __init__.py           # Package initialization
├── config.py             # Model configurations and settings
├── deploy.py             # Main deployment script
├── utils.py              # Utility functions (quota checking, etc.)
└── README.md             # This file
```

## Prerequisites

### 1. GCP Setup

1. **Enable Required APIs**:
   ```bash
   gcloud services enable aiplatform.googleapis.com
   gcloud services enable compute.googleapis.com
   ```

2. **Service Account Permissions**:
   The service account whose key is in **GCP_SA_KEY** (used by GitHub Actions) must have these roles on the project:
   - `roles/aiplatform.user` - Required for `aiplatform.endpoints.create`, model upload, and deploy
   - `roles/storage.objectViewer` - To read model files from GCS
   - `roles/iam.serviceAccountUser` - To deploy as the runtime service account (GCP_SERVICE_ACCOUNT)

   **If the pipeline fails with "Permission 'aiplatform.endpoints.create' denied"**, grant the pipeline service account the Vertex AI User role:
   ```bash
   # Replace SA_EMAIL with the email of the service account used in GCP_SA_KEY
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:SA_EMAIL" \
     --role="roles/aiplatform.user"
   ```

3. **Quota Requirements**:
   - GPU quota for your chosen accelerator type (e.g., NVIDIA_L4, NVIDIA_A100)
   - Check quota at: https://console.cloud.google.com/iam-admin/quotas

### 2. Environment Variables

Set these environment variables:

```bash
# Required
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
export GCP_SERVICE_ACCOUNT="your-service-account@your-project.iam.gserviceaccount.com"

# Optional: For loading models from GCS (same as GitHub secrets)
# POLYPHEMUS_MODEL_PATH = parent path to the model folder; POLYPHEMUS_DEFAULT_MODEL = folder name
# Example: model at gs://your-bucket-name/cache/your-model-name → POLYPHEMUS_MODEL_PATH=gs://your-bucket-name/cache, POLYPHEMUS_DEFAULT_MODEL=your-model-name
export POLYPHEMUS_MODEL_PATH="gs://your-bucket-name/cache"
export POLYPHEMUS_DEFAULT_MODEL="your-model-name"

# Optional: For private HuggingFace models
export HF_TOKEN="hf_your_token_here"
```

Or create a `.env` file in the `model_deployment` directory (see `.env.example`):

```bash
GCP_PROJECT_ID=your-project-id
GCP_REGION=us-central1
GCP_SERVICE_ACCOUNT=your-service-account@your-project.iam.gserviceaccount.com
POLYPHEMUS_MODEL_PATH=gs://your-bucket-name/cache
POLYPHEMUS_DEFAULT_MODEL=your-model-name
HF_TOKEN=hf_your_token_here
```

### 3. Python Dependencies

Dependencies are defined in `apps/polyphemus/pyproject.toml` under the optional group `vertex-ai`. Install and run using one of these options:

**Option A – From polyphemus root with vertex-ai extra (recommended):**

```bash
cd apps/polyphemus
uv sync --extra vertex-ai
uv run python -m model_deployment.deploy --help
```

**Option B – From model_deployment directory:**

```bash
cd apps/polyphemus/model_deployment
uv run --project .. python -m model_deployment.deploy --help
```

**Important:** Run the deploy module from `apps/polyphemus` (e.g. `uv run python -m model_deployment.deploy`) so that package imports resolve correctly.

## Configuration

### Model Configuration

Edit `config.py` to configure your models. Each model requires:

```python
{
    "model_name": "llama-3-1-8b-instruct",           # Display name
    "model_id": "meta-llama/Meta-Llama-3.1-8B-Instruct",  # HuggingFace ID OR GCS path
    "machine_type": "g2-standard-12",                # Machine type
    "accelerator_type": "NVIDIA_L4",                 # GPU type
    "accelerator_count": 1,                          # Number of GPUs
    "max_model_len": 4096,                          # Max sequence length
    "hf_token": "",                                 # Optional: HuggingFace token
}
```

#### Model Loading Options

The `model_id` field supports two options:

1. **HuggingFace Model ID** (downloaded at deployment time):
   ```python
   "model_id": "meta-llama/Meta-Llama-3.1-8B-Instruct"
   ```

2. **GCS Path** (pre-downloaded models, faster deployment):
   Set `POLYPHEMUS_MODEL_PATH` and `POLYPHEMUS_DEFAULT_MODEL` (e.g. `gs://your-bucket-name/models` and `your-model-name`). The full path `POLYPHEMUS_MODEL_PATH/POLYPHEMUS_DEFAULT_MODEL` is used as `model_id`.
   ```python
   "model_id": "gs://your-bucket-name/models/your-model-name"
   ```

**Recommendation**: Use the same `POLYPHEMUS_MODEL_PATH` and `POLYPHEMUS_DEFAULT_MODEL` as your Cloud Run / GitHub secrets for consistency. Pre-download your models to that GCS path in the same region as your deployment.

### Available Machine Types

Common machine types for GPU deployments:

| Machine Type | vCPUs | Memory | Recommended GPU |
|--------------|-------|--------|-----------------|
| g2-standard-4 | 4 | 16 GB | 1x NVIDIA_L4 |
| g2-standard-8 | 8 | 32 GB | 1x NVIDIA_L4 |
| g2-standard-12 | 12 | 48 GB | 1x NVIDIA_L4 |
| a2-highgpu-1g | 12 | 85 GB | 1x NVIDIA_A100 |
| a2-highgpu-2g | 24 | 170 GB | 2x NVIDIA_A100 |

### Available Accelerators

| Accelerator | Memory | Use Case |
|-------------|--------|----------|
| NVIDIA_L4 | 24 GB | Cost-effective, good for 7B-13B models |
| NVIDIA_A100 | 40 GB | High performance, for larger models |
| NVIDIA_TESLA_T4 | 16 GB | Budget option for smaller models |
| NVIDIA_TESLA_V100 | 16 GB | Legacy, good performance |

## Deployment

### Preparing Models in GCS (Recommended)

For faster deployments, pre-download your models to GCS:

```bash
# 1. Download model from HuggingFace
huggingface-cli download Goekdeniz-Guelmez/your-model-name \
  --local-dir ./model-cache

# 2. Upload to GCS
gsutil -m cp -r ./model-cache gs://vllm-model-storage/models/your-model-name

# 3. Update config.py to use GCS path
# model_id = "gs://vllm-model-storage/models/your-model-name"
```

**Benefits of GCS storage**:
- Faster deployment (no download time)
- No HuggingFace rate limits
- Consistent deployment times
- Better for production environments

### Local Deployment

Deploy models from your local machine:

```bash
cd apps/polyphemus
uv run python -m model_deployment.deploy
```

#### Deployment Options

```bash
# Deploy with default settings (skip existing deployments)
uv run python -m model_deployment.deploy

# Force redeployment even if models exist
uv run python -m model_deployment.deploy --force

# Enable LoRA support
uv run python -m model_deployment.deploy --enable-lora

# Enforce eager execution (disable CUDA graphs)
uv run python -m model_deployment.deploy --enforce-eager

# Set guided decoding backend
uv run python -m model_deployment.deploy --guided-decoding-backend=outlines
```

### GitHub Actions Deployment

#### Required Secrets

Configure these GitHub secrets for automated deployment:

**Required**:
- `PROJECT_ID` - GCP project ID
- `GCP_SA_KEY` - Service account key JSON
- `GCP_SERVICE_ACCOUNT` - Service account email
- `REGION` - Deployment region (e.g., us-central1)

**Optional (for GCS model loading)**:
- `POLYPHEMUS_MODEL_PATH` - GCS parent path to the model folder (e.g. `gs://your-bucket-name/cache` for `gs://.../cache/your-model-name`)
- `POLYPHEMUS_MODEL_BUCKET` - GCS bucket name (optional; derived from POLYPHEMUS_MODEL_PATH if not set)
- `POLYPHEMUS_DEFAULT_MODEL` - Model folder name (e.g. your-model-name)
- `HUGGINGFACE_TOKEN` - HuggingFace token for private models

#### Deployment Methods

1. **Automatic Deployment** (on push to main):
   ```bash
   git add apps/polyphemus/model_deployment/
   git commit -m "feat: update model deployment config"
   git push origin main
   ```

2. **Manual Deployment** (workflow_dispatch):
   - Go to: Actions → [Deploy] Polyphemus Model Deployment
   - Click "Run workflow"
   - Select options:
     - Environment (dev/stg/prd)
     - Skip existing deployments
     - Enable LoRA
     - Enforce eager
     - Guided decoding backend

### Monitoring Deployment

1. **Check logs** in GitHub Actions or terminal output
2. **View endpoints** in Vertex AI Console:
   ```
   https://console.cloud.google.com/vertex-ai/endpoints?project=YOUR_PROJECT_ID
   ```
3. **Test endpoints** using the Python client (see below)

## Usage

Deployed vLLM models expose the **OpenAI chat-completions** API at `/v1/chat/completions`. Polyphemus (and the examples below) call the Vertex AI **`:rawPredict`** API and send the **raw** request body (no `instances` envelope). The container forwards that body to `/v1/chat/completions` and returns the OpenAI-style response.

### Python Client

Use `:rawPredict` with the raw OpenAI-style JSON body (messages, max_tokens, temperature, etc.):

```python
import google.auth
import google.auth.transport.requests
import httpx

PROJECT_ID = "your-project-id"
LOCATION = "us-central1"
ENDPOINT_ID = "your-endpoint-id"  # from: gcloud ai endpoints list --region=us-central1

# Get ADC token
creds, _ = google.auth.default()
creds.refresh(google.auth.transport.requests.Request())
token = creds.token

url = (
    f"https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}"
    f"/locations/{LOCATION}/endpoints/{ENDPOINT_ID}:rawPredict"
)
body = {
    "messages": [{"role": "user", "content": "Hello, how are you?"}],
    "max_tokens": 100,
    "temperature": 0.7,
}
with httpx.Client(timeout=60.0) as client:
    response = client.post(
        url,
        json=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
response.raise_for_status()
data = response.json()
# OpenAI-style response: choices, usage
print(data["choices"][0]["message"]["content"])
```

### REST API

Get the endpoint ID:

```bash
gcloud ai endpoints list --region=us-central1 --project=YOUR_PROJECT_ID
```

Call **`:rawPredict`** with the raw chat-completions JSON (no `instances` wrapper):

```bash
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  https://REGION-aiplatform.googleapis.com/v1/projects/PROJECT_ID/locations/REGION/endpoints/ENDPOINT_ID:rawPredict \
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 100,
    "temperature": 0.7
  }'
```

Response is OpenAI-style: `choices`, `usage`, etc.

## Cost Optimization

### Tips to Reduce Costs

1. **Right-size your machine types**: Start with smaller machines (e.g., g2-standard-4) and scale up if needed
2. **Use appropriate GPUs**: L4 is more cost-effective than A100 for most workloads
3. **Set min/max instances**: Configure autoscaling to scale to zero when not in use
4. **Delete unused endpoints**: Clean up endpoints you're not using

### Estimated Costs

Approximate hourly costs (as of 2024):

| Configuration | Cost/hour |
|---------------|-----------|
| g2-standard-8 + 1x L4 | ~$1.50 |
| a2-highgpu-1g + 1x A100 | ~$4.50 |

**Note**: Costs may vary by region and are subject to change. Check [GCP Pricing](https://cloud.google.com/vertex-ai/pricing) for current rates.

## Troubleshooting

### Common Issues

#### 1. Insufficient Quota

**Error**: `Quota exceeded for quota metric 'GPUS_ALL_REGIONS'`

**Solution**:
- Request quota increase: https://console.cloud.google.com/iam-admin/quotas
- Try a different region with available quota
- Use a different GPU type

#### 2. Deployment Timeout

**Error**: `Deployment timed out after 1800 seconds`

**Solution**:
- Large models may take longer to download and initialize
- Ensure your model files are in GCS in the same region as deployment
- Check Cloud Logging for detailed error messages

#### 3. Permission Denied (e.g. `aiplatform.endpoints.create` denied)

**Error**: `403 Permission 'aiplatform.endpoints.create' denied on resource ...`

**Solution**:
- The service account in **GCP_SA_KEY** (used by GitHub Actions) needs `roles/aiplatform.user` on the project.
- Grant it:
  ```bash
  gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:YOUR_PIPELINE_SA_EMAIL" \
    --role="roles/aiplatform.user"
  ```
- Also ensure APIs are enabled and the account can access model files in GCS.

#### 4. Out of Memory

**Error**: `OOM (Out of Memory) during model loading`

**Solution**:
- Use a larger machine type
- Increase GPU count
- Reduce `max_model_len` in config
- Enable `enforce_eager` to reduce memory overhead

### Debug Mode

Enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Comparison: Cloud Run vs Vertex AI

| Feature | Cloud Run (Existing) | Vertex AI (New) |
|---------|---------------------|----------------|
| **Use Case** | API service with custom logic | Managed ML model endpoints |
| **Scaling** | Auto-scales based on requests | Auto-scales, supports GPU |
| **GPU Support** | Limited (1 GPU per instance) | Full support, multiple GPUs |
| **Cost** | Pay per request + GPU time | Pay per endpoint uptime |
| **Deployment** | Docker container | Model upload + endpoint |
| **vLLM Optimization** | Self-managed | Managed by Vertex AI |
| **Best For** | Application logic + small models | Large models, high throughput |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Polyphemus Service                    │
└─────────────────────────────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          │                     │
    ┌─────▼──────┐      ┌──────▼──────┐
    │ Cloud Run  │      │ Vertex AI   │
    │            │      │             │
    │ - API      │      │ - ML Models │
    │ - Logic    │      │ - vLLM      │
    │            │      │ - Multi-GPU │
    └────────────┘      └─────────────┘
                              │
                              │                     
                              │
                     ┌────────▼────────┐
                     │   GCS Bucket    │
                     │  (Model Files)  │
                     └─────────────────┘
```

## Additional Resources

- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [vLLM Documentation](https://docs.vllm.ai/)
- [HuggingFace Models](https://huggingface.co/models)
- [GCP Pricing Calculator](https://cloud.google.com/products/calculator)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Cloud Logging for detailed error messages
3. Consult the Vertex AI documentation
4. Open an issue in the repository
