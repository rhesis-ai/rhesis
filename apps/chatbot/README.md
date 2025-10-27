# Rhesis Insurance Chatbot (Rosalind)

Default insurance chatbot endpoint for new user onboarding. Provides instant access to explore Rhesis AI capabilities without configuration.

## Overview

Rosalind is a pre-configured insurance expert chatbot powered by Google's Gemini AI. This service eliminates onboarding friction by allowing new users to immediately interact with a working AI application.

## Features

- **Zero Configuration**: Works out of the box for all new users
- **Dual-Tier Rate Limiting**:
  - **Authenticated Access**: 1000 requests/day per user (with API key + user headers)
  - **Public Access**: 100 requests/day per IP (no authentication required)
- **Secure Backend Integration**: API key authentication for backend services
- **Per-User Rate Limiting**: Track usage per user/organization when authenticated
- **Domain-Specific**: Trained specifically for insurance-related queries
- **Session Management**: Maintains conversation context across multiple messages
- **Health Monitoring**: Built-in health check endpoint for service monitoring

## Quick Start

### Local Development

1. **Install dependencies:**

```bash
# Install uv if you don't have it
pip install uv

# Sync dependencies
uv sync
```

2. **Set environment variables:**

```bash
# Model Configuration (uses SDK providers)
export DEFAULT_GENERATION_MODEL="vertex_ai"  # Or "gemini", "openai", etc.
export DEFAULT_MODEL_NAME="gemini-2.0-flash"  # Recommended - faster than 2.5

# Vertex AI Configuration (if using vertex_ai provider)
export GOOGLE_APPLICATION_CREDENTIALS="base64-encoded-json-or-file-path"
export VERTEX_AI_LOCATION="europe-west4"  # Netherlands (best for Europe - has gemini-2.0-flash)
export VERTEX_AI_PROJECT=""  # Optional: auto-extracted from credentials

# Alternative: Gemini API (if using gemini provider)
export GEMINI_API_KEY="your-gemini-api-key"
export GEMINI_MODEL_NAME="gemini-2.0-flash-001"

# Rate Limiting
export CHATBOT_RATE_LIMIT="1000"  # Optional, defaults to 1000 requests/day for authenticated users
export CHATBOT_API_KEY="your-secret-api-key"  # Optional, enables backend authentication
```

3. **Run the server:**

```bash
# Development mode (activates virtual environment automatically)
uv run uvicorn client:app --reload --port 8080

# Or activate the virtual environment manually
source .venv/bin/activate
uvicorn client:app --reload --port 8080

# Production mode with Gunicorn
uv run gunicorn --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080 client:app
```

4. **Test the chatbot:**

```bash
# Health check
curl http://localhost:8080/health

# Send a chat message
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is term life insurance?"}'
```

### Docker Build

```bash
# Build the image from repo root (includes SDK dependency)
cd /path/to/rhesis
docker build -t rhesis-chatbot -f apps/chatbot/Dockerfile .

# Run the container with Vertex AI (recommended)
docker run -p 8080:8080 \
  -e DEFAULT_GENERATION_MODEL="vertex_ai" \
  -e DEFAULT_MODEL_NAME="gemini-2.0-flash" \
  -e GOOGLE_APPLICATION_CREDENTIALS="base64-encoded-credentials" \
  -e VERTEX_AI_LOCATION="europe-west4" \
  -e CHATBOT_RATE_LIMIT="1000" \
  rhesis-chatbot

# Or with Gemini API (alternative)
docker run -p 8080:8080 \
  -e DEFAULT_GENERATION_MODEL="gemini" \
  -e DEFAULT_MODEL_NAME="gemini-2.0-flash-001" \
  -e GEMINI_API_KEY="your-api-key" \
  -e CHATBOT_RATE_LIMIT="1000" \
  rhesis-chatbot
```

## API Endpoints

### POST /chat

Main chat interaction endpoint.

**Request:**
```json
{
  "message": "What is the difference between term life and whole life insurance?",
  "session_id": "optional-session-id",
  "use_case": "insurance"
}
```

**Response:**
```json
{
  "message": "Assistant response text...",
  "session_id": "abc123-def456-ghi789",
  "context": ["Context fragment 1", "Context fragment 2"],
  "use_case": "insurance"
}
```

### GET /health

Health check endpoint for monitoring.

**Response:**
```json
{
  "status": "healthy",
  "service": "rhesis-insurance-chatbot",
  "version": "1.0.0"
}
```

### GET /

API information and available endpoints.

### GET /sessions/{session_id}

Retrieve conversation history.

### DELETE /sessions/{session_id}

Delete a conversation session.

### GET /use-cases

List available use cases (currently only "insurance").

## Configuration

### Environment Variables

- `GEMINI_API_KEY` (required): Google Gemini API key
- `GEMINI_MODEL_NAME` (optional): Model to use, defaults to "gemini-2.0-flash-001"
- `CHATBOT_RATE_LIMIT` (optional): Maximum requests per day for authenticated users, defaults to 1000
- `CHATBOT_API_KEY` (optional): API key for backend authentication. Enables dual-tier rate limiting (1000/day authenticated, 100/day public)
- `PORT` (optional): Server port, defaults to 8080

### Rate Limiting

The chatbot implements **dual-tier rate limiting** based on authentication:

#### **Tier 1: Authenticated Access** ✅ **Recommended for Backend**
- **1000 requests/day per user** (configurable via `CHATBOT_RATE_LIMIT`)
- Requires `Authorization: Bearer <CHATBOT_API_KEY>` header
- Requires `X-User-ID` and/or `X-Organization-ID` headers for per-user tracking
- Each user gets their own quota - prevents one user from exhausting limits for others
- Cannot be spoofed without valid API key

#### **Tier 2: Public Access**
- **100 requests/day per IP address** (fixed limit)
- No authentication required
- Useful for demos, testing, and public evaluation
- Stricter limits to prevent abuse

To modify authenticated user rate limits:

```bash
# Set to 2000 requests per day for authenticated users
export CHATBOT_RATE_LIMIT="2000"

# Or in Docker
docker run -e CHATBOT_RATE_LIMIT="2000" ...

# Or in Cloud Run deployment
gcloud run deploy ... --set-env-vars CHATBOT_RATE_LIMIT=2000
```

**Note**: Public access limit (100/day per IP) is fixed and cannot be configured.

### Authentication

The chatbot supports **optional API key authentication** for backend services, enabling secure per-user rate limiting:

#### **Mode 1: Public Only (No API Key)** 
- All requests treated as public access
- 100 requests/day per IP address
- No user-level tracking
- Good for demos and testing

#### **Mode 2: Dual-Tier with Authentication** ✅ **Recommended**
Set the `CHATBOT_API_KEY` environment variable:

```bash
export CHATBOT_API_KEY="your-secret-key-here"
```

**Authenticated Backend Requests** (Higher Limits):
```bash
curl -X POST http://localhost:8080/chat \
  -H "Authorization: Bearer your-secret-key-here" \
  -H "X-User-ID: user-123" \
  -H "X-Organization-ID: org-456" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is term life insurance?"}'
```

Benefits:
- ✅ 1000 requests/day per user
- ✅ Per-user/organization tracking
- ✅ Cannot be spoofed (requires valid API key)
- ✅ Fair usage across all users

**Public Requests** (Lower Limits):
```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is term life insurance?"}'
```

- 100 requests/day per IP
- No authentication required
- Good for public demos

**Error Responses:**

Invalid API key (401):
```json
{
  "detail": "Invalid API key. Public access available with rate limit of 100 requests/day."
}
```

Rate limit exceeded (429):
```json
{
  "detail": "Rate limit exceeded. Retry after X seconds."
}
```

**Note**: 
- The `/health`, `/`, and `/use-cases` endpoints are always accessible without authentication
- The root endpoint (`/`) only displays authentication information when `CHATBOT_API_KEY` is configured
- No sensitive information (like the actual API key) is ever exposed in API responses

## Use Cases

The chatbot supports multiple use cases through the `use_cases/` directory. Each `.md` file defines a system prompt for a specific domain.

### Current Use Cases

- **insurance.md**: Insurance expert (Rosalind) - default and primary use case

### Adding New Use Cases

1. Create a new `.md` file in `use_cases/` directory (e.g., `legal.md`)
2. Write the system prompt defining the AI's personality and expertise
3. Use it by passing `"use_case": "legal"` in API requests

Example system prompt:

```markdown
Your name is Lex. You are a friendly legal expert here to answer questions about law.
Your responses should be clear, concise, and conversational.
Keep your tone professional but approachable.
The answers should be up to 100 words.
If the user asks a question not related to law, politely explain your area of expertise.
You should answer in fluid text, no new lines or breaks.
Do not use markdown formatting.
```

## Architecture

```
apps/chatbot/
├── client.py          # FastAPI application with endpoints
├── endpoint.py        # Core logic for Gemini interaction and response generation
├── chatbot.py         # [Legacy] Original implementation
├── use_cases/         # System prompts for different domains
│   ├── insurance.md   # Rosalind - Insurance expert
│   ├── finance.md     # Financial advisor
│   ├── health.md      # Health advisor
│   └── legal.md       # Legal advisor
├── Dockerfile         # Container build configuration
├── pyproject.toml     # Project configuration and dependencies
├── uv.lock           # Locked dependency versions
└── README.md          # This file
```

### Key Components

**client.py**
- FastAPI application setup
- API endpoint definitions
- Rate limiting configuration
- Session management
- Request/response handling

**endpoint.py**
- `GeminiClient`: Wrapper for Google Gemini API with retry logic
- `ResponseGenerator`: Handles prompt processing and response generation
- Context generation for enhanced responses
- Error handling and fallbacks

## Deployment

### GitHub Actions

Automatic deployment is configured via `.github/workflows/chatbot.yml`:

- Triggers on push to `main` with changes to `apps/chatbot/**`
- Supports manual deployment with environment selection
- Builds and pushes Docker image to GCR
- Deploys to Google Cloud Run

### Manual Deployment to Cloud Run

```bash
# Build and tag (from repo root)
docker build -t gcr.io/PROJECT_ID/rhesis-chatbot:latest -f apps/chatbot/Dockerfile .

# Push to GCR
docker push gcr.io/PROJECT_ID/rhesis-chatbot:latest

# Deploy to Cloud Run
gcloud run deploy rhesis-chatbot \
  --image gcr.io/PROJECT_ID/rhesis-chatbot:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --cpu 1 \
  --max-instances 10 \
  --min-instances 0 \
  --set-env-vars GEMINI_API_KEY=your-key,CHATBOT_RATE_LIMIT=1000,CHATBOT_API_KEY=your-secret-key
```

## Monitoring

### Health Checks

The service includes Docker health checks:

```bash
# Manual health check
curl http://your-service-url/health
```

### Logs

View logs in Cloud Run console or using gcloud:

```bash
gcloud run services logs read rhesis-chatbot --region us-central1
```

### Metrics to Monitor

- Request rate and latency
- Rate limit violations (429 responses)
- Error rates (500 responses)
- Gemini API failures
- Session count and memory usage

## Troubleshooting

### Common Issues

**"Gemini API key is required" error**
- Ensure `GEMINI_API_KEY` environment variable is set
- Verify the API key is valid and has quota

**Rate limit errors (429)**
- Normal for high-traffic scenarios
- Users should implement exponential backoff
- Consider adjusting rate limits for your use case

**Slow responses**
- Gemini API latency varies by load
- Consider response caching for common queries
- Check Gemini API quota and limits

**Session not found (404)**
- Sessions are stored in memory and cleared on restart
- Implement persistent storage (Redis, database) for production

## Development

### Testing

```python
# Test basic chat (with authentication if required)
import requests

headers = {
    "Content-Type": "application/json",
}

# Add authentication header if CHATBOT_API_KEY is set
api_key = "your-secret-api-key"  # Replace with your actual key
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"

response = requests.post(
    "http://localhost:8080/chat",
    headers=headers,
    json={"message": "What is homeowners insurance?"}
)
print(response.json())
```

### Code Quality

```bash
# Format code
black .

# Type checking
mypy client.py endpoint.py

# Linting
flake8 .
```

## Security Considerations

- API keys are passed via environment variables, never hardcoded
- Rate limiting prevents abuse
- CORS headers should be configured for production use
- Consider adding authentication for production deployments
- Session data is stored in memory (not persisted)

## Future Enhancements

- [ ] Add authentication middleware for per-user rate limits
- [ ] Implement Redis for persistent session storage
- [ ] Add response caching for common queries
- [ ] Support streaming responses for real-time chat
- [ ] Add conversation analytics and logging
- [ ] Multi-language support
- [ ] Custom rate limits per user tier
- [ ] Integration with Rhesis backend for user management

## Contributing

1. Make changes in a feature branch
2. Test locally with Docker
3. Update documentation as needed
4. Create pull request with clear description

## License

See LICENSE file in repository root.

## Support

For issues or questions:
- GitHub Issues: https://github.com/rhesis-ai/rhesis/issues
- Documentation: https://docs.rhesis.ai/platform/default-chatbot

