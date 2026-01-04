# Rhesis Telemetry Examples

This folder contains practical examples demonstrating how to use OpenTelemetry tracing in the Rhesis SDK.

## Examples

### 1. Basic Usage (No Framework)
**File**: `basic_example.py`

Demonstrates:
- Using `@observe` decorator for tracing functions
- Semantic layer constants (`AIOperationType`)
- Custom span attributes
- Nested trace hierarchies
- **Rhesis handles LLM calls automatically with Gemini** (no OpenAI/Anthropic needed)
- HTTP-only observability (no WebSocket needed)

**Use Case**: When you want pure observability without external AI frameworks.

### 2. FastAPI Server (Production-like)
**File**: `fastapi_example.py`

Demonstrates:
- Real FastAPI application with traced endpoints
- HTTP API requests → OpenTelemetry traces
- Trace hierarchies from nested operations
- Health checks and chat endpoints
- **Production-ready patterns**

**Use Case**: When you want to see telemetry in a real API server context.

### 3. LangChain Auto-Instrumentation
**File**: `langchain_example.py`

Demonstrates:
- Auto-instrumentation with `auto_instrument()`
- Automatic LLM and tool tracing via callbacks
- Zero-config observability
- Integration with existing LangChain code
- **Using Gemini via LangChain's Google Generative AI integration**

**Use Case**: When you're using LangChain and want automatic tracing without code changes.

## Prerequisites

This project uses `uv` for package management. Install it first:

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Note**: Dependencies are managed via `pyproject.toml` in this directory. The local development SDK (`../../sdk`) is automatically used.

No external LLM SDKs needed for the basic example! Rhesis handles LLM calls using Gemini by default.

## Installing Dependencies (Optional)

If you want to install dependencies explicitly instead of letting `uv run` handle it:

```bash
cd examples/telemetry

# Install base dependencies
uv sync

# Install with LangChain support
uv sync --extra langchain
```

## Prerequisites - Start the Backend

**Before running examples**, make sure the Rhesis backend is running:

```bash
# From the project root
docker compose up -d

# Check backend is running
curl http://localhost:8080/health
```

The backend receives traces on `POST /telemetry/traces`.

## Configuration

Set your environment variables:

```bash
# Required: Rhesis backend credentials
export RHESIS_API_KEY="your-api-key"
export RHESIS_PROJECT_ID="your-project-id"

# Required for LangChain example: Google Gemini API key
export GOOGLE_API_KEY="your-gemini-api-key"
```

**Important**: 
- All examples require `RHESIS_API_KEY` and `RHESIS_PROJECT_ID` to send traces
- Make sure your **backend is running** (default: `http://localhost:8080`)
- The LangChain example also requires `GOOGLE_API_KEY` for Gemini access
- Without backend, traces are created locally but not sent anywhere

Or configure in code:

```python
from rhesis.sdk import RhesisClient

client = RhesisClient(
    api_key="your-api-key",
    project_id="your-project-id",
    environment="development",
)
```

## Running the Examples

```bash
cd examples/telemetry

# Basic example (no frameworks)
uv run basic_example.py

# FastAPI server (production-like)
uv run --extra fastapi fastapi_example.py
# Then test with:
# curl http://localhost:8000/chat -X POST -H "Content-Type: application/json" \
#   -d '{"input": "What is the weather like?", "session_id": "test-123"}'

# LangChain example (auto-instrumentation)
uv run --extra langchain langchain_example.py
```

**How it works**: `uv run` automatically:
- Reads `pyproject.toml` in this directory
- Installs the local SDK from `../../sdk`
- Creates an isolated environment
- Installs all dependencies
- Runs the script

On first run, it will install dependencies (may take a minute). Subsequent runs are instant!

### Testing the FastAPI Example

Once the FastAPI server is running, test the endpoints:

```bash
# Health check (simple traced request)
curl http://localhost:8000/health

# Chat endpoint (complex trace hierarchy)
curl http://localhost:8000/chat \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "input": "What is the weather like today?",
    "session_id": "demo-session-123",
    "temperature": 0.7
  }'

# API documentation (interactive)
open http://localhost:8000/docs
```

**What you'll see in traces:**
- `function.chat_endpoint` (root span from @observe on the endpoint)
  - `ai.retrieval` (fetch_user_context)
  - `ai.tool.invoke` (check_weather)
  - `ai.llm.invoke` (call_llm)

## What You'll See

### In the Backend Dashboard
After running the examples, traces will appear in your Rhesis dashboard:
- **Span hierarchy** showing function calls and nesting
- **Timing information** for each operation (latency, duration)
- **LLM usage** (model, tokens, prompts, completions)
- **Tool invocations** with inputs/outputs
- **Custom attributes** (temperature, model, session_id)
- **HTTP context** (for FastAPI: method, path, status code)

### In the Console
The examples print:
- Function execution results
- Trace IDs for debugging
- Span information
- Request/response details (FastAPI example)

### FastAPI Example Benefits
The FastAPI example shows **production-ready patterns**:
- ✅ Real HTTP API with traced endpoints
- ✅ Automatic request context in spans
- ✅ Error handling with traced exceptions
- ✅ Health checks (with minimal overhead)
- ✅ Interactive API docs at `/docs`
- ✅ Realistic nested operations (context → weather → LLM)

## Architecture

### Trace Flow

```
┌─────────────────────────────────┐
│ Your Application                │
│  @observe() decorator           │
└────────────┬────────────────────┘
             │
             ▼ (OpenTelemetry)
┌─────────────────────────────────┐
│ BatchSpanProcessor              │
│  - Collects spans in memory     │
│  - Batches every 5 seconds      │
└────────────┬────────────────────┘
             │
             ▼ HTTP POST
┌─────────────────────────────────┐
│ Rhesis Backend                  │
│  POST /telemetry/traces         │
│  - Validates spans              │
│  - Stores in PostgreSQL         │
│  - Available in dashboard       │
└─────────────────────────────────┘
```

### Decorator Overview

| Feature | `@observe` |
|---------|------------|
| **Tracing** | ✅ Yes |
| **WebSocket** | ❌ No |
| **HTTP (traces)** | ✅ Yes |
| **Backend Required** | ❌ No |
| **Use Case** | Any function you want to trace |

## Key Concepts

### 1. Semantic Layer

Always use constants from `AIOperationType`:

```python
from rhesis.sdk.telemetry.schemas import AIOperationType

@observe(span_name=AIOperationType.LLM_INVOKE)  # ✅ Good
# Not: @observe(span_name="ai.llm.invoke")      # ❌ Bad
```

Available constants:
- `AIOperationType.LLM_INVOKE` - LLM calls
- `AIOperationType.TOOL_INVOKE` - Tool/function calls
- `AIOperationType.RETRIEVAL` - Vector search/RAG
- `AIOperationType.EMBEDDING_GENERATE` - Embedding creation

### 2. Span Attributes

Add rich context to your spans:

```python
@observe(
    span_name=AIOperationType.LLM_INVOKE,
    model="gpt-4",
    temperature=0.7,
    max_tokens=150
)
def call_llm(prompt: str) -> str:
    return openai.chat.completions.create(...)
```

### 3. Auto-Instrumentation

For frameworks like LangChain, use auto-instrumentation:

```python
from rhesis.sdk.telemetry import auto_instrument

# Automatically trace all LangChain operations
auto_instrument()

# Now your existing LangChain code is traced!
chain = LLMChain(llm=ChatOpenAI(), prompt=prompt)
result = chain.run("What is AI?")
```

### 4. Batching

Spans are batched and sent every 5 seconds:
- **Max queue**: 2048 spans
- **Max batch**: 512 spans per request
- **Interval**: 5 seconds

This means traces may appear with a slight delay.

## Best Practices

### 1. Use `@observe` for Any Function You Want to Trace

```python
@observe(span_name=AIOperationType.LLM_INVOKE)
def call_llm(prompt: str) -> str:
    """Traced LLM call."""
    return llm.generate(prompt)

@observe(span_name=AIOperationType.TOOL_INVOKE)
def fetch_data(query: str) -> dict:
    """Traced tool invocation."""
    return database.query(query)
```

### 2. Create Trace Hierarchies

```python
@observe()  # Root span
def process_request(input: str) -> dict:
    """Parent function creates root span."""
    context = fetch_data(input)  # Child span
    response = call_llm(input)    # Child span
    return {"response": response, "context": context}
```

### 3. Add Rich Attributes

```python
@observe(
    span_name=AIOperationType.LLM_INVOKE,
    model="gpt-4-turbo",
    temperature=0.7,
    max_tokens=500,
    user_id="user-123",
    conversation_id="conv-456"
)
def call_llm_with_context(prompt: str, user_id: str) -> str:
    return openai.chat.completions.create(...)
```

### 4. Use Auto-Instrumentation for Frameworks

```python
# At the start of your application
from rhesis.sdk.telemetry import auto_instrument

auto_instrument()  # Automatically traces LangChain, LangGraph, etc.

# Now all framework operations are traced automatically
```

## Troubleshooting

### Traces Not Appearing

1. **Wait 5 seconds** - Spans are batched
2. **Check backend connectivity** - `curl http://localhost:8080/telemetry/traces`
3. **Enable debug logging**:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```
4. **Verify span names** - Use `AIOperationType` constants

### Connection Issues

- `@observe` only needs HTTP connection to backend
- Ensure backend is running (default: `http://localhost:8080`)
- Check `POST /telemetry/traces` endpoint is accessible

### High Memory Usage

Reduce batching configuration:
```python
from opentelemetry.sdk.trace.export import BatchSpanProcessor

span_processor = BatchSpanProcessor(
    exporter,
    max_queue_size=512,         # Reduced from 2048
    schedule_delay_millis=2000, # Export every 2s instead of 5s
)
```

## Learn More

- **[Semantic Layer](../../playground/telemetry/SEMANTIC_LAYER.md)** - AI conventions and constants
- **[How Telemetry Works](../../playground/telemetry/HOW_TELEMETRY_WORKS.md)** - Technical architecture
- **[SDK Usage Guide](../../playground/telemetry/SDK_USAGE_GUIDE.md)** - Complete developer guide
- **[WP4 Auto-Instrumentation](../../playground/telemetry/WP4_AUTO_INSTRUMENTATION.md)** - Implementation details

## Support

For questions or issues:
1. Check the documentation links above
2. Review the examples in this folder
3. Enable debug logging to see trace export details

