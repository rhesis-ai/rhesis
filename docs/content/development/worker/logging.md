import { CodeBlock } from '@/components/CodeBlock'

# Worker Logging Guide

This guide covers everything about logging in the Rhesis worker system, from configuration to analysis and troubleshooting.

## Overview

The worker system generates logs from multiple sources:
- **Celery Worker**: Task execution, queue processing, worker lifecycle
- **Health Server**: HTTP health checks, debugging endpoints
- **Startup Script**: Container initialization, environment validation
- **Application Code**: Task-specific logging from your business logic

## Log Configuration

### Environment Variables

Control logging behavior with these environment variables:

```bash
# Primary log level (affects all components)
LOG_LEVEL=INFO

# Celery-specific log level
CELERY_WORKER_LOGLEVEL=INFO

# Python logging configuration
PYTHONUNBUFFERED=1  # Ensures immediate log output
```

**Available Log Levels:**
- `DEBUG`: Detailed debugging information
- `INFO`: General operational messages (recommended)
- `WARNING`: Warning messages for potential issues
- `ERROR`: Error conditions that don't stop execution
- `CRITICAL`: Serious errors that may stop execution

### Celery Logging Configuration

In the worker startup, Celery is configured with:

```bash
celery -A rhesis.backend.worker.app worker \
    --loglevel=${CELERY_WORKER_LOGLEVEL:-INFO} \
    --concurrency=${CELERY_WORKER_CONCURRENCY:-8} \
    # ... other options
```

## Log Sources and Formats

### 1. Startup Script Logs

**Location**: Container stdout during initialization
**Format**: Structured with emoji indicators and timestamps

```bash
# Successful operations
✅ Health server starting on port 8080
✅ Successfully imported Celery app from rhesis.backend.worker
✅ Redis connectivity: connected

# Warnings
⚠️  TLS detected in broker URL, adjusting timeouts to 5 seconds

# Errors
❌ Failed to import Celery app: No module named 'rhesis.backend.worker'
❌ Redis connectivity test failed: connection timeout
```

### 2. Health Server Logs

**Location**: Container stdout from health server process
**Format**: HTTP access logs with endpoint information

```bash
# Successful health checks
INFO:     127.0.0.1:35492 - "GET /health/basic HTTP/1.1" 200 OK
INFO:     127.0.0.1:35494 - "GET /health HTTP/1.1" 200 OK

# Health check failures
WARNING:  127.0.0.1:35496 - "GET /health HTTP/1.1" 500 Internal Server Error
ERROR:    Health check failed: Redis connection timeout

# Debug endpoint usage
INFO:     127.0.0.1:35498 - "GET /debug HTTP/1.1" 200 OK
INFO:     127.0.0.1:35500 - "GET /debug/redis HTTP/1.1" 200 OK
```

### 3. Celery Worker Logs

**Location**: Container stdout from Celery process
**Format**: Celery's standard logging format with task information

```bash
# Worker startup
[2024-01-15 10:30:00,123: INFO/MainProcess] Connected to redis://redis-host:6379/0
[2024-01-15 10:30:00,456: INFO/MainProcess] mingle: searching for available workers
[2024-01-15 10:30:01,789: INFO/MainProcess] celery@worker-pod ready.

# Task processing
[2024-01-15 10:30:15,234: INFO/MainProcess] Received task: rhesis.backend.tasks.execute_test[task-id-123]
[2024-01-15 10:30:15,456: INFO/ForkPoolWorker-1] Task rhesis.backend.tasks.execute_test[task-id-123] succeeded in 2.34s
[2024-01-15 10:30:16,789: INFO/MainProcess] Received task: rhesis.backend.tasks.collect_results[chord-id-456]

# Errors
[2024-01-15 10:30:20,123: ERROR/ForkPoolWorker-2] Task rhesis.backend.tasks.execute_test[task-id-789] raised unexpected: ConnectionError('Redis connection failed')
[2024-01-15 10:30:25,456: WARNING/MainProcess] Chord unlock task chord_unlock[chord-id-456] retry: Retry in 1.0s
```

### 4. Application Task Logs

**Location**: Container stdout from your task code
**Format**: Python logging format as configured in your tasks

```python
# In your task code
import logging

logger = logging.getLogger(__name__)

@app.task(base=BaseTask)
def my_task(self):
    logger.info(f"Starting task for organization: {self.request.organization_id}")
    try:
        # Task logic
        result = process_data()
        logger.info(f"Task completed successfully: {result}")
        return result
    except Exception as e:
        logger.error(f"Task failed: {str(e)}")
        raise
```

## Accessing Logs

### Local Development

```bash
# Using Docker Compose
docker-compose logs worker

# Follow logs in real-time
docker-compose logs -f worker

# Get last N lines
docker-compose logs --tail=100 worker
```

### GKE Deployment

#### Basic Log Access
```bash
# Get logs from worker container
kubectl logs <pod-name> -c worker -n <namespace>

# Get recent logs (last 100 lines)
kubectl logs <pod-name> -c worker -n <namespace> --tail=100

# Get logs from last hour
kubectl logs <pod-name> -c worker -n <namespace> --since=1h
```

#### Real-Time Monitoring
```bash
# Follow logs as they're generated
kubectl logs -f <pod-name> -c worker -n <namespace>

# Follow logs from all worker pods
kubectl logs -f deployment/rhesis-worker -n <namespace>

# Follow logs from all containers in pod
kubectl logs -f <pod-name> -n <namespace> --all-containers=true
```

#### Historical Logs
```bash
# Get logs from previous container restart (if crashed)
kubectl logs <pod-name> -c worker -n <namespace> --previous

# Get logs with timestamps
kubectl logs <pod-name> -c worker -n <namespace> --timestamps=true
```

## Log Analysis Techniques

### 1. Finding Your Pods

```bash
# List all worker pods
kubectl get pods -n <namespace> -l app=rhesis-worker

# Get pod details including restart count
kubectl get pods -n <namespace> -o wide
```

### 2. Filtering Logs

#### Search for Errors
```bash
# Find all errors
kubectl logs <pod-name> -c worker -n <namespace> | grep -i error

# Find Redis connection issues
kubectl logs <pod-name> -c worker -n <namespace> | grep -i "redis\|connection\|timeout"

# Find task failures
kubectl logs <pod-name> -c worker -n <namespace> | grep -E "(failed|exception|error)"
```

#### Search for Task Activity
```bash
# Find task executions
kubectl logs <pod-name> -c worker -n <namespace> | grep "Received task"

# Find task completions
kubectl logs <pod-name> -c worker -n <namespace> | grep "succeeded in"

# Find chord activity
kubectl logs <pod-name> -c worker -n <namespace> | grep -i chord
```

#### Search for Health Check Activity
```bash
# Find health check requests
kubectl logs <pod-name> -c worker -n <namespace> | grep -E "(GET /health|GET /ping)"

# Find health check failures
kubectl logs <pod-name> -c worker -n <namespace> | grep -E "(500|timeout|failed)"
```

### 3. Advanced Log Analysis

#### Export Logs for Analysis
```bash
# Save logs to file
kubectl logs <pod-name> -c worker -n <namespace> --tail=1000 > worker-logs.txt

# Save logs with timestamps
kubectl logs <pod-name> -c worker -n <namespace> --timestamps=true --tail=1000 > worker-logs-timestamped.txt

# Save logs from specific time period
kubectl logs <pod-name> -c worker -n <namespace> --since=2h > recent-worker-logs.txt
```

#### Multi-Pod Log Aggregation
```bash
# Get logs from all worker pods
for pod in $(kubectl get pods -n <namespace> -l app=rhesis-worker -o jsonpath='{.items[*].metadata.name}'); do
  echo "=== Logs from $pod ===" >> all-worker-logs.txt
  kubectl logs $pod -c worker -n <namespace> --tail=100 >> all-worker-logs.txt
  echo "" >> all-worker-logs.txt
done
```

## Log Patterns and What They Mean

### Healthy Worker Startup
```bash
✅ Health server starting on port 8080
✅ Environment validation completed
✅ Successfully imported Celery app
✅ Redis connectivity: connected
✅ Health server ready, all endpoints responding
[INFO/MainProcess] Connected to rediss://...
[INFO/MainProcess] celery@worker-pod ready.
```

### Common Warning Patterns
```bash
# TLS connection delay (normal for Redis TLS)
⚠️  TLS detected in broker URL, adjusting timeouts to 10 seconds

# Chord retries (may indicate failed subtasks)
[WARNING/MainProcess] Chord unlock task chord_unlock[...] retry: Retry in 1.0s

# Health check timeouts (may indicate Redis delays)
WARNING: Health check took 8.5 seconds (timeout: 10)
```

### Error Patterns to Investigate

#### Connection Errors
```bash
❌ Redis connectivity test failed: connection timeout
[ERROR/MainProcess] consumer: Cannot connect to rediss://...: Error connecting
```
**Action**: Check Redis connectivity, network policies, firewall rules

#### Import Errors
```bash
❌ Failed to import Celery app: No module named 'rhesis.backend.worker'
```
**Action**: Check Docker image build, PYTHONPATH configuration

#### Task Errors
```bash
[ERROR/ForkPoolWorker-1] Task rhesis.backend.tasks.execute_test[...] raised unexpected: Exception('Task failed')
```
**Action**: Check task code, input parameters, database connectivity

#### Health Check Errors
```bash
ERROR: Health check failed: Celery ping timeout after 10 seconds
INFO: 127.0.0.1:42756 - "GET /health HTTP/1.1" 500 Internal Server Error
```
**Action**: Check Celery worker status, Redis connectivity

## Log Monitoring and Alerting

### Key Metrics to Monitor

1. **Error Rate**: Frequency of ERROR/CRITICAL log entries
2. **Health Check Failures**: HTTP 500 responses on `/health`
3. **Connection Timeouts**: Redis/broker connectivity issues
4. **Task Failure Rate**: Ratio of failed to successful tasks
5. **Worker Restarts**: Container restart frequency

### Sample Monitoring Queries

#### Using kubectl and basic tools
```bash
# Count errors in last 100 log lines
kubectl logs <pod-name> -c worker -n <namespace> --tail=100 | grep -c ERROR

# Check for recent connection issues
kubectl logs <pod-name> -c worker -n <namespace> --since=10m | grep -i "connection\|timeout"

# Monitor health check success rate
kubectl logs <pod-name> -c worker -n <namespace> --since=1h | grep "GET /health" | grep -c "200 OK"
```

#### Log-based Health Check
```bash
#!/bin/bash
# Simple health check based on logs
NAMESPACE="rhesis-worker-dev"
POD=$(kubectl get pods -n $NAMESPACE -l app=rhesis-worker -o jsonpath='{.items[0].metadata.name}')

# Check for recent errors
ERROR_COUNT=$(kubectl logs $POD -c worker -n $NAMESPACE --tail=50 | grep -c ERROR)
if [ $ERROR_COUNT -gt 5 ]; then
    echo "WARNING: $ERROR_COUNT errors found in recent logs"
fi

# Check for Redis connectivity
REDIS_ERRORS=$(kubectl logs $POD -c worker -n $NAMESPACE --since=5m | grep -c "Redis\|connection")
if [ $REDIS_ERRORS -gt 0 ]; then
    echo "WARNING: Redis connection issues detected"
fi
```

## Debugging with Logs

### Step-by-Step Debugging Process

1. **Identify the Problem**
   ```bash
   # Check pod status
   kubectl get pods -n <namespace>

   # Look for restart indicators
   kubectl describe pod <pod-name> -n <namespace>
   ```

2. **Get Recent Logs**
   ```bash
   # Get current logs
   kubectl logs <pod-name> -c worker -n <namespace> --tail=100

   # Get crash logs if restarted
   kubectl logs <pod-name> -c worker -n <namespace> --previous
   ```

3. **Search for Specific Issues**
   ```bash
   # Connection problems
   kubectl logs <pod-name> -c worker -n <namespace> | grep -i "connection\|redis\|timeout"

   # Task problems
   kubectl logs <pod-name> -c worker -n <namespace> | grep -i "task\|error\|failed"
   ```

4. **Correlate with Health Endpoints**
   ```bash
   # Check current system state
   kubectl exec -it <pod-name> -n <namespace> -- curl localhost:8080/debug | jq
   ```

### Common Debugging Scenarios

#### Scenario 1: Pod Won't Start
```bash
# Check startup logs
kubectl logs <pod-name> -c worker -n <namespace>

# Look for import errors, connection failures, configuration issues
kubectl logs <pod-name> -c worker -n <namespace> | grep -E "(❌|ERROR|Failed)"
```

#### Scenario 2: Health Checks Failing
```bash
# Check health endpoint logs
kubectl logs <pod-name> -c worker -n <namespace> | grep -E "(GET /health|500|timeout)"

# Test health endpoint directly
kubectl exec -it <pod-name> -n <namespace> -- curl -w "%{time_total}" localhost:8080/health
```

#### Scenario 3: Tasks Not Processing
```bash
# Check for task reception
kubectl logs <pod-name> -c worker -n <namespace> | grep "Received task"

# Check for task failures
kubectl logs <pod-name> -c worker -n <namespace> | grep -E "(failed|exception|error)"

# Check worker status
kubectl exec -it <pod-name> -n <namespace> -- curl localhost:8080/debug | jq '.celery_status'
```

## Best Practices

### 1. Log Retention
- Keep logs for at least 7 days for troubleshooting
- Archive important logs before pod restarts
- Use log aggregation systems for production

### 2. Log Levels
- Use `INFO` for production (balance of detail vs. noise)
- Use `DEBUG` for development and troubleshooting
- Use `ERROR` only for actual errors that need attention

### 3. Structured Logging
- Include relevant context (organization_id, user_id, task_id)
- Use consistent log formats across tasks
- Include timing information for performance monitoring

### 4. Log Monitoring
- Set up alerts for error rate increases
- Monitor health check failure patterns
- Track connection timeout frequencies

### 5. Performance Considerations
- Avoid excessive logging in tight loops
- Use appropriate log levels to control verbosity
- Consider log sampling for high-volume operations

## Integration with Other Tools

### Health Endpoints
The logging system integrates with the health endpoints:
- `/debug`: Shows system status including recent errors
- `/debug/redis`: Shows Redis connectivity with error details
- All endpoints log their usage for monitoring

### Monitoring Systems
Logs can be integrated with:
- **Prometheus**: Metric extraction from log patterns
- **Grafana**: Log visualization and dashboards
- **ELK Stack**: Centralized log aggregation and search
- **Google Cloud Logging**: Native GKE log collection

### Alert Integration
Example alert conditions based on logs:
- Error rate > 10% over 5 minutes
- Health check failure rate > 20% over 2 minutes
- No successful task processing for 10 minutes
- Redis connection timeouts > 5 in 5 minutes

This comprehensive logging system provides visibility into all aspects of worker operation, from startup through task processing to health monitoring.
