# Polyphemus

Rhesis's adversarial model used to generate tests that commercial off-the-shelf models will not generate. Polyphemus enables comprehensive testing of AI systems by producing challenging test cases that explore edge cases, adversarial scenarios, and sensitive topics that typical LLMs may refuse or handle poorly.

## Environment Variables

The following environment variables are required for Polyphemus to function:

### Required

- `JWT_SECRET_KEY`: JWT secret key for service delegation token validation. **MUST match the JWT_SECRET_KEY in the backend service.**

### Optional

- `MODEL_PATH`: Path to the model weights (if using local models)
- `DEFAULT_MODEL`: Default model to use (default: "default")
- `LOAD_KWARGS_B64`: Base64-encoded JSON string of model loading kwargs

## Authentication

Polyphemus supports two authentication methods:

1. **API Tokens (rh-*)**: User-initiated requests using Rhesis API tokens
2. **JWT Delegation Tokens**: Service-to-service requests from Backend/Worker that maintain user attribution

## Local Development

1. Create a `.env` file in `apps/polyphemus/` with:
   ```bash
   JWT_SECRET_KEY=<same-as-backend>
   DEFAULT_MODEL=default
   ```

2. Start the service:
   ```bash
   cd apps/polyphemus
   uv run uvicorn rhesis.polyphemus.main:app --reload --port 8000
   ```

## Deployment

Polyphemus is deployed to Google Cloud Run via GitHub Actions (`.github/workflows/polyphemus.yml`).

Required secrets in GitHub:
- `JWT_SECRET_KEY`: Shared secret for delegation token validation
- `MODEL_PATH`: Cloud Storage path to model weights
- `DEFAULT_MODEL`: Model identifier to use

