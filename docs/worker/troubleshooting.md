# Worker Troubleshooting Guide

This document covers common issues you may encounter with the Rhesis worker system and how to resolve them.

## Chord-Related Issues

> **📖 For comprehensive chord management, see [Chord Management and Monitoring](chord-management.md)**

The most common issues in the Rhesis worker system involve Celery chords. For detailed information about chord monitoring, troubleshooting, and best practices, refer to the dedicated [Chord Management Guide](chord-management.md).

### Quick Chord Issue Resolution

If you're experiencing chord issues right now:

1. **Immediate Check**: Run `python fix_chords.py` from the backend directory
2. **Status Overview**: Run `python -m rhesis.backend.tasks.execution.chord_monitor status`
3. **Emergency Cleanup**: See [Emergency Recovery](chord-management.md#emergency-recovery) section

## Dealing with Stuck Tasks

Sometimes tasks can get stuck in an infinite retry loop, especially chord tasks (`chord_unlock`) when subtasks fail. This can happen if:

1. One or more subtasks in a chord fail permanently
2. The broker connection is interrupted during a chord execution
3. The worker processes are killed unexpectedly

### Symptoms of Stuck Tasks

The most obvious symptom is thousands of repeated log entries like these:

```
Task celery.chord_unlock[82116cfc-ae23-4526-b7ff-7267f389b367] retry: Retry in 1.0s
MaxRetriesExceededError: Can't retry celery.chord_unlock[task-id] args:(...) kwargs:{...}
```

These messages indicate that there are "zombie" tasks that keep retrying indefinitely.

### Quick Resolution for Stuck Chords

> **💡 See [Chord Management Guide](chord-management.md) for comprehensive solutions**

```bash
# Check for stuck chords
python -m rhesis.backend.tasks.execution.chord_monitor check --max-hours 1

# Revoke stuck chords (dry run first)
python -m rhesis.backend.tasks.execution.chord_monitor revoke --max-hours 1 --dry-run

# Actually revoke them
python -m rhesis.backend.tasks.execution.chord_monitor revoke --max-hours 1
```

### Configuration to Prevent Stuck Tasks

The worker.py file includes configuration to limit chord retries:

```python
app.conf.update(
    # Chord configuration - prevent infinite retry loops
    chord_unlock_max_retries=3,
    chord_unlock_retry_delay=1.0,
    
    # Improved chord reliability
    result_persistent=True,
    result_expires=3600,
    
    # Task tracking for monitoring
    task_track_started=True,
    task_send_sent_event=True,
    worker_send_task_events=True,
)
```

Additionally, the results handling in `tasks/execution/results.py` includes logic to detect and handle failed subtasks:

```python
# Handle different result formats from chord execution
processed_results = []
if results:
    for result in results:
        if result is None:
            processed_results.append(None)
        elif isinstance(result, list) and len(result) == 2:
            # Handle [[task_id, result], error] format from failed chord tasks
            task_result = result[1] if result[1] is not None else None
            processed_results.append(task_result)
        else:
            processed_results.append(result)

# Check for failed tasks and count them
failed_tasks = sum(1 for result in processed_results 
                  if result is None or 
                  (isinstance(result, dict) and result.get("status") == "failed"))
```

### Purging Stuck Tasks

> **⚠️ Use these commands with caution in production**

For immediate relief from stuck tasks:

```bash
# Emergency: Purge all tasks (see chord-management.md for safer alternatives)
python -m rhesis.backend.tasks.execution.chord_monitor clean --force
```

For more targeted approaches, see the [Chord Management Guide](chord-management.md#monitoring-script-reference).

## Tenant Context Issues

If tasks fail with errors related to the tenant context, such as:

```
unrecognized configuration parameter "app.current_organization"
```

Ensure that:

1. Your database has the proper configuration parameters set
2. The `organization_id` and `user_id` are correctly passed to the task
3. The tenant context is explicitly set at the beginning of database operations

The `execute_single_test` task in `tasks/execution/test.py` includes defensive coding to handle such issues:

```python
# Access context from task request - task headers take precedence over kwargs
task = self.request
request_user_id = getattr(task, 'user_id', None)
request_org_id = getattr(task, 'organization_id', None)

# Use passed parameters if available, otherwise use request context
user_id = user_id or request_user_id
organization_id = organization_id or request_org_id
```

## Common Worker Errors

### Error: "chord_unlock" task failing repeatedly

**Symptoms**: Repeated logs of chord_unlock tasks retrying, MaxRetriesExceededError

**Cause**: This typically happens when one or more subtasks in a chord (group of tasks) fail, but the callback still needs to run

**Solution**: 
1. Use the monitoring script: `python fix_chords.py`
2. See [Chord Management Guide](chord-management.md#common-chord-issues) for detailed solutions
3. Ensure tasks always return valid results (see [best practices](chord-management.md#task-implementation-best-practices))

### Error: No connection to broker

**Symptoms**: Worker fails to start or tasks are not being processed

**Cause**: Connection to the Redis broker is not working

**Solution**:
1. Check that Redis is running and accessible
2. Verify the `BROKER_URL` environment variable is correct
3. For TLS connections (`rediss://`), ensure `ssl_cert_reqs=CERT_NONE` parameter is included
4. Test Redis connectivity: `redis-cli -u "$BROKER_URL" ping`
5. Check firewall rules if running in a cloud environment
6. For GKE deployments, see the [GKE Troubleshooting Guide](gke-troubleshooting.md)

### Error: Missing API Keys for Model Evaluation

**Symptoms**: Tasks fail with errors like "GEMINI_API_KEY environment variable is required"

**Cause**: Model evaluation tasks require API keys for external AI services

**Solution**:
1. Ensure the following environment variables are set:
   - `GEMINI_API_KEY`: For Google Gemini models
   - `GEMINI_MODEL_NAME`: Gemini model name (e.g., "gemini-1.5-pro")
   - `AZURE_OPENAI_ENDPOINT`: Azure OpenAI endpoint URL
   - `AZURE_OPENAI_API_KEY`: Azure OpenAI API key
   - `AZURE_OPENAI_DEPLOYMENT_NAME`: Your Azure deployment name
   - `AZURE_OPENAI_API_VERSION`: API version (e.g., "2024-02-01")
2. For GKE deployments, add these to your GitHub secrets
3. Verify environment variables using the debug endpoint: `curl localhost:8080/debug/env`

### Error: Test runs stuck in "IN_PROGRESS" status

**Symptoms**: Test configurations start but never complete, remain in progress indefinitely

**Cause**: Usually chord-related - the callback function (`collect_results`) never executes

**Solution**:
1. Check for stuck chords: `python -m rhesis.backend.tasks.execution.chord_monitor status`
2. See [Chord Never Completing](chord-management.md#2-chord-never-completing) in the Chord Management Guide
3. Review individual task results to ensure they're returning valid data

## Worker Registration and Status Checking

### Check Registered Workers

Use this Python script to check if workers are properly registered with the Celery broker:

```bash
# Create check_workers.py in project root
cat > check_workers.py << 'EOF'
#!/usr/bin/env python3
import os
import sys
from datetime import datetime

sys.path.insert(0, 'apps/backend/src')

try:
    from rhesis.backend.worker import app as celery_app
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def check_celery_workers():
    print("🚀 CELERY WORKER CHECKER")
    print("=" * 50)
    print(f"⏰ Timestamp: {datetime.now().isoformat()}")
    
    try:
        inspect = celery_app.control.inspect()
        
        # Check active workers
        print("\n📋 Active Workers:")
        active = inspect.active()
        if active:
            for worker_name, tasks in active.items():
                print(f"  ✅ {worker_name}: {len(tasks)} active tasks")
        else:
            print("  ❌ No active workers found")
        
        # Check registered workers
        print("\n📋 Registered Workers:")
        registered = inspect.registered()
        if registered:
            for worker_name, tasks in registered.items():
                print(f"  ✅ {worker_name}: {len(tasks)} registered tasks")
        else:
            print("  ❌ No registered workers found")
        
        # Check worker stats
        print("\n📊 Worker Statistics:")
        stats = inspect.stats()
        if stats:
            for worker_name, worker_stats in stats.items():
                print(f"  📈 {worker_name}:")
                print(f"    - Pool: {worker_stats.get('pool', {}).get('max-concurrency', 'unknown')} max concurrency")
                print(f"    - Total tasks: {worker_stats.get('total', 'unknown')}")
        else:
            print("  ❌ No worker statistics available")
        
        return bool(active or registered)
        
    except Exception as e:
        print(f"❌ Error checking Celery workers: {e}")
        return False

if __name__ == "__main__":
    check_celery_workers()
EOF

chmod +x check_workers.py
```

**Usage:**
```bash
python check_workers.py
```

**Expected Output (healthy workers):**
```
🚀 CELERY WORKER CHECKER
==================================================
⏰ Timestamp: 2025-06-14T10:57:41.278363

📋 Active Workers:
  ✅ celery@worker-pod-abc123: 0 active tasks

📋 Registered Workers:
  ✅ celery@worker-pod-abc123: 12 registered tasks

📊 Worker Statistics:
  📈 celery@worker-pod-abc123:
    - Pool: 8 max concurrency
    - Total tasks: 0
```

**Expected Output (no workers):**
```
📋 Active Workers:
  ❌ No active workers found

📋 Registered Workers:
  ❌ No registered workers found

📊 Worker Statistics:
  ❌ No worker statistics available
```

### Quick Worker Status Commands

```bash
# Check if any workers are running
python -c "from rhesis.backend.worker import app; print('Workers:', list(app.control.inspect().active().keys()) if app.control.inspect().active() else 'None')"

# Get worker statistics
python -c "from rhesis.backend.worker import app; import json; print(json.dumps(app.control.inspect().stats(), indent=2))"

# Check registered tasks
python -c "from rhesis.backend.worker import app; registered = app.control.inspect().registered(); print(f'Registered tasks: {sum(len(tasks) for tasks in registered.values()) if registered else 0}')"
```

### Worker Connection Troubleshooting

If no workers are found:

1. **Check broker connectivity:**
   ```bash
   python -c "
   import os
   import redis
   from urllib.parse import urlparse
   
   broker_url = os.getenv('BROKER_URL')
   parsed = urlparse(broker_url)
   r = redis.Redis(host=parsed.hostname, port=parsed.port, password=parsed.password, ssl=(parsed.scheme=='rediss'))
   print('Redis ping:', r.ping())
   "
   ```

2. **Verify worker processes are running:**
   ```bash
   # For local development
   ps aux | grep celery
   
   # For Docker/Kubernetes
   kubectl get pods -n <namespace>
   kubectl logs <pod-name> -n <namespace>
   ```

3. **Check worker startup logs:**
   ```bash
   # Look for successful worker registration
   grep -i "ready" /path/to/worker/logs
   grep -i "connected" /path/to/worker/logs
   ```

## Monitoring and Prevention

### Regular Monitoring

Set up automated monitoring to catch issues early:

```bash
# Add to crontab for periodic monitoring
*/15 * * * * cd /path/to/backend && python fix_chords.py >/dev/null 2>&1
```

### Health Checks

Include chord status in your application health checks:

```python
from rhesis.backend.tasks.execution.chord_monitor import get_active_chord_unlocks, check_stuck_chords

def worker_health_check():
    active_chords = get_active_chord_unlocks()
    stuck_chords = check_stuck_chords(max_runtime_hours=1)
    
    return {
        "status": "unhealthy" if stuck_chords else "healthy",
        "active_chord_unlocks": len(active_chords),
        "stuck_chords": len(stuck_chords)
    }
```

## Related Documentation

- **[Chord Management and Monitoring](chord-management.md)**: Comprehensive guide for chord-specific issues
- **[GKE Troubleshooting Guide](gke-troubleshooting.md)**: Debugging workers in Google Kubernetes Engine
- [Background Tasks and Processing](background-tasks.md): General task management information
- [Architecture and Dependencies](architecture.md): System integration details 