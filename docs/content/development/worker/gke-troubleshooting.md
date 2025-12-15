import { CodeBlock } from '@/components/CodeBlock'

# GKE Worker Troubleshooting Guide

This guide covers troubleshooting Celery workers running in Google Kubernetes Engine (GKE), including using the built-in debugging tools.

## Quick Start: Connect to Your Cluster

### 1. Find Your Cluster
```bash
gcloud container clusters list --format="table(name,location,status)"
```

### 2. Get Credentials
```bash
gcloud container clusters get-credentials <cluster-name> --region=<region>
```

### 3. Install kubectl (if needed)
```bash
sudo apt-get update
sudo apt-get install -y kubectl google-cloud-cli-gke-gcloud-auth-plugin
```

## Health Check Endpoints

The worker includes several debugging endpoints:

| Endpoint | Purpose | Use Case |
|----------|---------|----------|
| `/ping` | Basic connectivity | Quick server test |
| `/health/basic` | Server health (no dependencies) | Readiness probe |
| `/health` | **Lightweight** health (Celery + Redis, no worker ping) | Liveness probe |
| `/debug` | Comprehensive system info | General debugging |
| `/debug/env` | Environment variables (sanitized) | Config issues |
| `/debug/redis` | Redis connectivity details | Connection problems |
| `/debug/detailed` | **Slow** health check with worker ping | Deep troubleshooting |

## Worker Registration Checking

### Check Registered Workers with Python Script

Create a Python script to check registered Celery workers and Redis connectivity:

```python
#!/usr/bin/env python3
"""
Script to check registered Celery workers
"""
import os
import sys
import json
from datetime import datetime

# Add the backend source to Python path
sys.path.insert(0, 'apps/backend/src')

try:
    from celery import Celery
    from rhesis.backend.worker import app as celery_app
    import redis
    from urllib.parse import urlparse
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're in the project root and have the required packages installed")
    sys.exit(1)

def parse_redis_url(url):
    """Parse Redis URL and return connection parameters"""
    parsed = urlparse(url)
    use_ssl = parsed.scheme == 'rediss'

    return {
        'host': parsed.hostname,
        'port': parsed.port or (6379 if not use_ssl else 6380),
        'password': parsed.password,
        'db': int(parsed.path.lstrip('/')) if parsed.path else 0,
        'ssl': use_ssl,
        'ssl_cert_reqs': None if use_ssl else None,
        'decode_responses': True
    }

def check_celery_workers():
    """Check Celery workers using the app's inspect functionality"""
    print("\n" + "="*50)
    print("🔍 CHECKING CELERY WORKERS")
    print("="*50)

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

        return True

    except Exception as e:
        print(f"❌ Error checking Celery workers: {e}")
        return False

def main():
    print("🚀 CELERY WORKER CHECKER")
    print("=" * 50)
    print(f"⏰ Timestamp: {datetime.now().isoformat()}")

    broker_url = os.getenv('BROKER_URL')
    if not broker_url:
        print("\n❌ BROKER_URL not found in environment")
        return

    print(f"🔗 Broker URL: {broker_url.split('@')[0]}@***")

    # Check Celery workers
    workers_found = check_celery_workers()

    print("\n" + "="*50)
    if workers_found:
        print("✅ WORKER CHECK COMPLETED - Workers found")
    else:
        print("⚠️  WORKER CHECK COMPLETED - No workers found")
    print("="*50)

if __name__ == "__main__":
    main()
```

**Usage:**
```bash
# Save as check_workers.py in project root
chmod +x check_workers.py
python check_workers.py
```

**Expected Output (with workers running):**
```
🚀 CELERY WORKER CHECKER
==================================================
⏰ Timestamp: 2025-06-14T10:57:41.278363
🔗 Broker URL: rediss://:***@***

==================================================
🔍 CHECKING CELERY WORKERS
==================================================

📋 Active Workers:
  ✅ celery@rhesis-worker-6d9bcd9c6f-abc123: 0 active tasks

📋 Registered Workers:
  ✅ celery@rhesis-worker-6d9bcd9c6f-abc123: 12 registered tasks

📊 Worker Statistics:
  📈 celery@rhesis-worker-6d9bcd9c6f-abc123:
    - Pool: 8 max concurrency
    - Total tasks: 0

==================================================
✅ WORKER CHECK COMPLETED - Workers found
==================================================
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

### Cluster Management Commands

**Scale workers down (for debugging):**
```bash
kubectl scale deployment rhesis-worker --replicas=0 -n <namespace>
```

**Scale workers back up:**
```bash
kubectl scale deployment rhesis-worker --replicas=2 -n <namespace>
```

**Check current replica count:**
```bash
kubectl get deployment rhesis-worker -n <namespace>
```

## Common Troubleshooting Commands

### Check Pod Status
```bash
kubectl get pods -n <namespace>
```

**Expected Output:**
```
NAME                             READY   STATUS    RESTARTS   AGE
rhesis-worker-6d9bcd9c6f-6bxk8   2/2     Running   0          5m
rhesis-worker-6d9bcd9c6f-9kqwz   2/2     Running   0          3m
```

**Problem Indicators:**
- `1/2 Ready`: Worker container failing, cloudsql-proxy working
- `0/2 Ready`: Both containers failing
- `CrashLoopBackOff`: Container repeatedly failing
- High restart count: Ongoing issues

### Check Pod Events
```bash
kubectl describe pod <pod-name> -n <namespace>
```

Look for events section at the bottom:
- `Unhealthy`: Health check failures
- `Failed`: Container start failures
- `Killing`: Pod being terminated

### Test Basic Connectivity
```bash
kubectl exec -it <pod-name> -n <namespace> -- curl http://localhost:8080/ping
```

**Expected:** `pong`

**If this fails:**
- Health server not starting
- Port 8080 not listening
- Container networking issues

### Test Health Endpoints
```bash
# Basic health (no dependencies)
kubectl exec -it <pod-name> -n <namespace> -- curl http://localhost:8080/health/basic

# Full health (includes Celery)
kubectl exec -it <pod-name> -n <namespace> -- curl -m 10 http://localhost:8080/health
```

### Get Debug Information
```bash
# Comprehensive debug info
kubectl exec -it <pod-name> -n <namespace> -- curl http://localhost:8080/debug | jq

# Redis-specific debugging
kubectl exec -it <pod-name> -n <namespace> -- curl http://localhost:8080/debug/redis | jq

# Environment variables (sanitized)
kubectl exec -it <pod-name> -n <namespace> -- curl http://localhost:8080/debug/env | jq

# Detailed health check with worker ping (may be slow)
kubectl exec -it <pod-name> -n <namespace> -- curl -m 15 http://localhost:8080/debug/detailed | jq
```

## Common Issues and Solutions

### 1. Pods Stuck at 1/2 Ready

**Symptoms:**
```
NAME                             READY   STATUS    RESTARTS   AGE
rhesis-worker-586659994f-lldfn   1/2     Running   167        13h
```

**Diagnosis:**
```bash
kubectl exec -it <pod-name> -n <namespace> -- curl http://localhost:8080/debug
```

**Common Causes:**

#### A. Redis Connection Issues
```json
{
  "redis_connectivity": "connection_failed",
  "environment": {
    "tls_detected": true,
    "broker_url_type": "rediss://"
  }
}
```

**Solutions:**
- Check Redis URL format: `rediss://` for TLS, `redis://` for standard
- Verify SSL parameters: `ssl_cert_reqs=CERT_NONE`
- Check network policies allowing outbound connections
- Verify Redis service is accessible from GKE

#### B. Health Check Timeouts
```json
{
  "celery_status": {"worker_state": "importable"},
  "redis_connectivity": "timeout"
}
```

**Note:** As of the latest update, the main `/health` endpoint uses a **lightweight check** that doesn't ping workers. If you're still seeing timeouts:

**Solutions:**
- Check Redis connectivity specifically: `curl localhost:8080/debug/redis`
- Use detailed health check to test worker ping: `curl localhost:8080/debug/detailed`
- The `/health` endpoint should now be much faster since it doesn't wait for worker responses
- If `/health` is still slow, it's likely a Redis connection issue, not worker startup

#### C. Environment Configuration
```bash
kubectl exec -it <pod-name> -n <namespace> -- curl http://localhost:8080/debug/env
```

Check for:
- Missing environment variables
- Incorrect secret references
- Malformed URLs

### 2. CrashLoopBackOff

**Diagnosis:**
```bash
kubectl logs <pod-name> -n <namespace> --previous
```

**Common Causes:**

#### A. Import Errors
```
❌ Failed to import Celery app: No module named 'rhesis.backend.worker'
```

**Solutions:**
- Check PYTHONPATH in deployment
- Verify Docker image build process
- Ensure all dependencies installed

#### B. Connection Failures
```
❌ Broker connection failed: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**Solutions:**
- Check SSL certificate configuration
- Verify `ssl_cert_reqs=CERT_NONE` parameter
- Test Redis connectivity outside GKE

### 3. High Memory Usage

**Diagnosis:**
```bash
kubectl top pods -n <namespace>
kubectl exec -it <pod-name> -n <namespace> -- free -h
```

**Solutions:**
- Adjust `CELERY_WORKER_MAX_TASKS_PER_CHILD`
- Increase memory limits in deployment
- Monitor for memory leaks in tasks

### 4. Task Processing Issues

**Diagnosis:**
```bash
# Check if worker is receiving tasks
kubectl logs <pod-name> -n <namespace> | grep "Received task"

# Check worker stats
kubectl exec -it <pod-name> -n <namespace> -- \
  python -c "from rhesis.backend.worker import app; print(app.control.inspect().stats())"
```

## Advanced Debugging

### Interactive Shell Access
```bash
kubectl exec -it <pod-name> -n <namespace> -- bash
```

From inside the container:
```bash
# Test Redis connection manually
python -c "
import redis
import os
r = redis.Redis.from_url(os.getenv('BROKER_URL'))
print(r.ping())
"

# Test Celery import
python -c "
from rhesis.backend.worker import app
print(f'Tasks: {len(app.tasks)}')
print(f'Broker: {app.conf.broker_url}')
"

# Check network connectivity
nslookup <redis-hostname>
telnet <redis-hostname> 6378
```

### Monitor Logs in Real-Time
```bash
# Follow logs for all worker pods
kubectl logs -f deployment/rhesis-worker -n <namespace>

# Follow logs for specific container
kubectl logs -f <pod-name> -c worker -n <namespace>
```

### Network Debugging
```bash
# Check network policies
kubectl get networkpolicies -n <namespace>

# Test external connectivity
kubectl exec -it <pod-name> -n <namespace> -- nslookup google.com

# Check firewall rules (if applicable)
gcloud compute firewall-rules list --filter="direction=EGRESS"
```

## Performance Monitoring

### Resource Usage
```bash
# Pod resource usage
kubectl top pods -n <namespace>

# Node resource usage
kubectl top nodes

# Detailed resource info
kubectl describe pod <pod-name> -n <namespace> | grep -A 10 "Requests\|Limits"
```

### Health Check Performance
```bash
# Time health check responses
kubectl exec -it <pod-name> -n <namespace> -- \
  time curl http://localhost:8080/health

# Monitor health check frequency
kubectl get events -n <namespace> --field-selector involvedObject.name=<pod-name>
```

## Preventive Measures

### 1. Proper Resource Limits
```yaml
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "1000m"
```

### 2. Appropriate Health Check Timeouts
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 120  # Allow for TLS startup
  timeoutSeconds: 20        # Account for Redis delays
  periodSeconds: 45
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health/basic      # Fast, no dependencies
    port: 8080
  initialDelaySeconds: 15
  timeoutSeconds: 5
  periodSeconds: 10
  failureThreshold: 3
```

### 3. Monitoring and Alerting
```bash
# Set up monitoring for:
# - Pod restart frequency
# - Health check failure rates
# - Redis connection timeouts
# - Memory usage trends
```

## Emergency Procedures

### Force Pod Restart
```bash
kubectl delete pod <pod-name> -n <namespace>
```

### Scale Down/Up
```bash
kubectl scale deployment rhesis-worker --replicas=0 -n <namespace>
kubectl scale deployment rhesis-worker --replicas=2 -n <namespace>
```

### Emergency Debugging
```bash
# Create debug pod with same network
kubectl run debug-pod --image=gcr.io/PROJECT_ID/rhesis-worker:latest \
  --namespace=<namespace> --rm -it -- bash

# Test from debug pod
curl http://rhesis-worker-service:8080/debug
```

## Getting Help

When reporting issues, include:

1. **Cluster Information:**
   ```bash
   kubectl version
   kubectl get nodes
   ```

2. **Pod Status:**
   ```bash
   kubectl get pods -n <namespace> -o wide
   kubectl describe pod <pod-name> -n <namespace>
   ```

3. **Debug Output:**
   ```bash
   kubectl exec -it <pod-name> -n <namespace> -- \
     curl http://localhost:8080/debug | jq
   ```

4. **Recent Logs:**
   ```bash
   kubectl logs <pod-name> -n <namespace> --tail=100
   ```

5. **Configuration:**
   ```bash
   kubectl get deployment rhesis-worker -n <namespace> -o yaml
   ```

This comprehensive information will help quickly identify and resolve issues.
