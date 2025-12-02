# Multi-Instance SDK Connection Fix

## Problem Summary

When deploying the backend to Google Cloud Run with multiple container instances, SDK connections were failing with "SDK not connected" errors, despite the SDK successfully connecting and registering functions.

### Symptom

```
SDK logs: ✅ Connected successfully to wss://stg-api.rhesis.ai/connector/ws
Backend logs: ❌ SDK not connected: {project_id} in {environment}
```

## Root Cause

The issue occurred due to **container instance distribution** in Cloud Run's load balancer:

### Scenario

1. **SDK Connection** → Routes to **Container A**
   - Container A stores connection in local memory: `_connections[key] = websocket`
   - Container A stores marker in Redis: `ws:connection:{key} = "active"`

2. **API Invocation** (from UI) → Routes to **Container B** (different instance!)
   - Container B checks: `if key in self._connections` → **❌ Not found locally**
   - Returns error: "SDK not connected"
   - Meanwhile, Container A has the connection but never receives the request

### Why It Failed

The original implementation had **two critical flaws**:

1. **Connection check was local-only**
   ```python
   def is_connected(self, project_id: str, environment: str) -> bool:
       key = self.get_connection_key(project_id, environment)
       return key in self._connections  # ❌ Only checks THIS container
   ```

2. **Direct WebSocket send requires local connection**
   ```python
   # This only works if the WebSocket is in the SAME container
   await connection_manager.send_and_await_result(...)
   ```

## Solution Architecture

### Overview

Implemented **Redis-based RPC (Remote Procedure Call)** mechanism to enable cross-instance communication:

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   SDK Client    │────▶│ Container A  │     │  Container B    │
│                 │ WS  │              │     │                 │
└─────────────────┘     │ WebSocket ✓  │     │ No WebSocket    │
                        └──────────────┘     └─────────────────┘
                               │                      │
                               ▼                      ▼
                        ┌──────────────────────────────────┐
                        │           Redis                  │
                        │  ┌────────────────────────────┐  │
                        │  │ ws:rpc:requests (pub/sub)  │  │
                        │  │ ws:rpc:response:{id}       │  │
                        │  │ ws:connection:{key}        │  │
                        │  └────────────────────────────┘  │
                        └──────────────────────────────────┘
```

### Components

#### 1. Connection Tracking (Redis + Local Memory)

**File:** `apps/backend/src/rhesis/backend/app/services/connector/manager.py`

```python
async def is_connected(self, project_id: str, environment: str) -> bool:
    """Check if SDK is connected (checks local + Redis)."""
    key = self.get_connection_key(project_id, environment)
    
    # Fast path: check local first
    if key in self._connections:
        return True
    
    # Check Redis for connections on other instances
    if redis_manager.is_available:
        redis_key = f"ws:connection:{key}"
        exists = await redis_manager.client.exists(redis_key)
        if exists > 0:
            return True  # Connection exists on another instance
    
    return False
```

#### 2. Smart Routing Decision

**File:** `apps/backend/src/rhesis/backend/app/services/invokers/sdk_invoker.py`

```python
def _determine_invocation_context(self, project_id: str, environment: str):
    """Determine whether to use RPC or direct WebSocket."""
    
    # Check if connection exists locally
    connection_key = connection_manager.get_connection_key(project_id, environment)
    has_local_connection = connection_key in connection_manager._connections
    
    # Decision logic:
    # - Workers: always RPC (they never have WebSockets)
    # - Backend with local connection: use direct WebSocket (fast)
    # - Backend without local connection: use RPC (connection on another instance)
    use_rpc = is_worker or not has_local_connection
```

#### 3. RPC Communication Flow

**Publish-Subscribe Pattern via Redis:**

1. **Request Publishing**
   ```python
   # Container B publishes request
   await redis.publish("ws:rpc:requests", {
       "request_id": "invoke_abc123",
       "project_id": "...",
       "environment": "staging",
       "function_name": "chat_with_history",
       "inputs": {...}
   })
   ```

2. **Request Listening** (All containers listen)
   ```python
   # Container A listens to channel
   async for message in pubsub.listen():
       request = json.loads(message["data"])
       
       # Check if I have this WebSocket
       if connection_key in self._connections:
           # Forward to SDK via WebSocket
           await websocket.send_json(...)
   ```

3. **Response Publishing**
   ```python
   # Container A publishes response back
   await redis.publish(f"ws:rpc:response:{request_id}", {
       "status": "success",
       "output": {...},
       "duration_ms": 4243.4
   })
   ```

4. **Response Retrieval**
   ```python
   # Container B subscribes and waits for response
   async for message in pubsub.listen():
       if message["type"] == "message":
           result = json.loads(message["data"])
           return result
   ```

## Implementation Details

### Files Modified

1. **`apps/backend/src/rhesis/backend/app/services/connector/manager.py`**
   - Made `is_connected()` async and Redis-aware
   - Added RPC listener: `_listen_for_rpc_requests()`
   - Stores connections in both local memory and Redis

2. **`apps/backend/src/rhesis/backend/app/services/invokers/sdk_invoker.py`**
   - Added smart routing logic
   - Uses direct WebSocket when connection is local
   - Falls back to RPC when connection is remote
   - Refactored into focused helper methods

3. **`apps/backend/src/rhesis/backend/app/routers/connector.py`**
   - Updated to await async `is_connected()` method

4. **`apps/backend/src/rhesis/backend/app/main.py`**
   - Initializes Redis on startup
   - Starts RPC listener background task

### Performance Optimization

The solution **optimizes for the common case**:

- **Local connection** (same container): Direct WebSocket → ~1ms overhead
- **Remote connection** (different container): RPC via Redis → ~5-10ms overhead

This means:
- ✅ Single-instance deployments: No Redis overhead
- ✅ Multi-instance with sticky sessions: Mostly direct WebSocket
- ✅ Multi-instance with random routing: RPC works correctly

## Testing

### Local Testing

With Redis available locally, the system intelligently uses direct WebSocket:

```bash
# Start Redis
docker compose up -d redis

# Start backend
cd apps/backend && uv run uvicorn ...

# Result: Uses direct WebSocket (connection is local)
INFO - SDK invocation context: BACKEND (direct WebSocket connection)
```

### Multi-Instance Testing

Deploy to Cloud Run with multiple instances:

```bash
# SDK connects to Instance A
INFO - Connected: {project_id}:{environment}

# API call hits Instance B
INFO - SDK invocation context: BACKEND (RPC via Redis - connection on another instance)
INFO - ✅ RPC client initialized successfully
INFO - Published RPC request: invoke_abc123
INFO - Received RPC response: invoke_abc123
```

## Configuration

### Environment Variables

- `BROKER_URL`: Redis connection string (default: `redis://localhost:6379/0`)
- No additional configuration needed - works automatically

### Redis Keys

- `ws:connection:{project_id}:{environment}`: Connection marker (TTL: 1 hour)
- `ws:rpc:requests`: Pub/sub channel for RPC requests
- `ws:rpc:response:{request_id}`: Pub/sub channel for individual responses

## Failure Modes & Fallbacks

### Redis Unavailable

**Behavior:** Falls back to local-only mode

```python
if not redis_manager.is_available:
    logger.warning("Redis not available - multi-instance support disabled")
    # Only works if SDK connects to same container
```

### Worker Context

**Behavior:** Always uses RPC (workers never have WebSocket connections)

```python
is_worker = os.getenv("CELERY_WORKER_NAME") is not None
if is_worker:
    use_rpc = True  # Must use RPC
```

### Connection Not Found Anywhere

**Behavior:** Returns clear error message

```json
{
  "error": true,
  "error_type": "sdk_not_connected",
  "message": "SDK client is not currently connected"
}
```

## Security Considerations

### Sensitive Data Redaction

Added comprehensive logging filter to prevent exposure of credentials:

**File:** `apps/backend/src/rhesis/backend/logging/rhesis_logger.py`

Redacts:
- Authorization headers (Bearer tokens, API keys)
- JWT tokens
- Session tokens
- Database credentials
- Cloud provider keys (AWS, GCP)

Applied to:
- websockets logger
- uvicorn logger
- fastapi logger

## Monitoring

### Key Metrics to Track

1. **Connection Distribution**
   ```python
   # How many connections per instance
   len(connection_manager._connections)
   ```

2. **RPC vs Direct Ratio**
   ```python
   # Log analysis
   grep "BACKEND (RPC via Redis" vs "BACKEND (direct WebSocket"
   ```

3. **RPC Latency**
   ```python
   # Response time for RPC calls
   duration_ms from RPC responses
   ```

## Troubleshooting

### "SDK not connected" in Multi-Instance

**Check:**
1. Redis is running and accessible
2. RPC listener is started: `grep "RPC LISTENER STARTED" logs`
3. Connection exists in Redis: `redis-cli GET ws:connection:{key}`

### High Latency

**Check:**
1. Are most requests using RPC? (Should prefer direct WebSocket)
2. Redis network latency
3. Consider sticky sessions on load balancer

### Memory Leaks

**Mitigation:**
- Old test results cleaned up automatically (max 10,000 entries)
- Connections removed from Redis on disconnect
- WebSocket connections have TTL in Redis (1 hour)

## Future Improvements

1. **Sticky Sessions**: Configure Cloud Run load balancer for session affinity
2. **Health Checks**: Monitor RPC listener health
3. **Metrics**: Add Prometheus metrics for RPC calls
4. **Connection Pool**: Reuse Redis connections more efficiently

## References

- Original Issue: Multi-instance SDK connection failures in Cloud Run
- Branch: `fix/backend-execution-rpc`
- Commits:
  - `41386dad`: Initial multi-instance connection fix
  - `f5facf20`: Improved local connection detection
  - `f4adf7a0`: Refactored SDK invoker for better organization
  - `a5583b64`: Added sensitive data redaction

## Credits

- **Problem Identified**: 2024-12-02
- **Solution Implemented**: 2024-12-02
- **Status**: ✅ Fixed and deployed

