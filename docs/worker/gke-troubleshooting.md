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
| `/health` | Full health (includes Celery + Redis) | Liveness probe |
| `/debug` | Comprehensive system info | General debugging |
| `/debug/env` | Environment variables (sanitized) | Config issues |
| `/debug/redis` | Redis connectivity details | Connection problems |

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

**Solutions:**
- Increase liveness probe timeout in deployment.yaml
- Check for TLS handshake delays
- Verify DNS resolution for Redis hostname

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