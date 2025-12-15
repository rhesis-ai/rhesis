import { CodeBlock } from '@/components/CodeBlock'

# Rhesis Worker Documentation

This directory contains documentation related to the Rhesis worker system, which handles background processing, task queues, and asynchronous operations using **Redis as the message broker**.

## Contents

- [Background Tasks and Processing](background-tasks.md): Detailed information about Redis-based Celery configuration, task management, tenant context handling, error recovery, and troubleshooting.
- [Chord Management and Monitoring](chord-management.md): Comprehensive guide to managing Celery chords, including monitoring tools, troubleshooting workflows, and best practices.
- [Chord Monitoring Quick Reference](chord-monitoring-quick-reference.md): Quick reference card for chord monitoring commands and workflows.
- [Troubleshooting Guide](troubleshooting.md): Solutions for common issues with workers, tasks, and the Celery processing system.
- [GKE Troubleshooting Guide](gke-troubleshooting.md): **NEW** - Comprehensive guide for diagnosing and fixing worker issues in Google Kubernetes Engine.
- [Logging Guide](logging.md): **NEW** - Complete guide to worker logging, log analysis, and monitoring.
- [Architecture and Dependencies](architecture.md): Explanation of how the worker system integrates with the backend and SDK components.

## Topics Covered

- **Redis-based Celery configuration** with TLS support
- Worker deployment and scaling in **GKE (Google Kubernetes Engine)**
- Task management and organization
- **Chord execution and monitoring**
- **Chord troubleshooting and recovery**
- Multi-tenancy in background tasks
- Error handling and recovery
- Task monitoring and observability
- **GKE troubleshooting with kubectl**
- **Comprehensive logging and log analysis**
- Redis connection diagnostics

## Quick Start Guides

### For Worker Registration Issues
If workers aren't processing tasks or seem disconnected:

1. **Check Worker Status**: Create and run `check_workers.py` (see [Worker Registration](troubleshooting.md#worker-registration-and-status-checking))
2. **Quick Status**: `python -c "from rhesis.backend.worker import app; print('Workers:', list(app.control.inspect().active().keys()) if app.control.inspect().active() else 'None')"`
3. **Test Redis Connection**: Verify broker connectivity
4. **Scale Workers**: `kubectl scale deployment rhesis-worker --replicas=0/2 -n <namespace>` (for GKE)

### For GKE Worker Issues
If you're experiencing deployment or connectivity issues:

1. **Connect to Cluster**: Follow [GKE Setup](gke-troubleshooting.md#quick-start-connect-to-your-cluster)
2. **Check Pod Status**: `kubectl get pods -n <namespace>`
3. **Check Logs**: `kubectl logs <pod> -c worker -n <namespace> --tail=100`
4. **Test Health Endpoints**: `kubectl exec -it <pod> -- curl localhost:8080/debug`
5. **Check Worker Registration**: Use [Worker Registration Checking](gke-troubleshooting.md#worker-registration-checking)
6. **Full Diagnostics**: See [GKE Troubleshooting Guide](gke-troubleshooting.md) and [Logging Guide](logging.md)

### For Chord Monitoring Issues
If you're experiencing chord-related issues:

1. **Quick Status Check**: Run `python fix_chords.py` from the backend directory
2. **Detailed Monitoring**: Use `python -m rhesis.backend.tasks.execution.chord_monitor status`
3. **Emergency Recovery**: See [Chord Management Guide](chord-management.md#emergency-recovery)
4. **Command Reference**: Check [Quick Reference](chord-monitoring-quick-reference.md) for all commands

## Related Documentation

- [Backend API Documentation](https://docs.rhesis.ai/development/backend): Information about the API services that queue background tasks
