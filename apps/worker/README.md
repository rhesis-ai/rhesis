# Celery Task Management Scripts

This directory contains utility scripts for managing and troubleshooting Celery tasks in your application.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [🚀 Quick Reference](#-quick-reference)
  - [🚨 Emergency Commands](#-emergency-commands)
  - [📊 Status Checking](#-status-checking)
  - [🛑 Stopping Tasks](#-stopping-tasks)
  - [🔍 System Health Check](#-system-health-check)
  - [⚡ Quick Diagnostics](#-quick-diagnostics)
  - [🎯 Success Indicators](#-success-indicators)
- [Scripts](#scripts)
- [Common Scenarios](#common-scenarios)
- [Understanding Task States](#understanding-task-states)
- [Troubleshooting Guide](#troubleshooting-guide)
- [Best Practices](#best-practices)
- [Configuration](#configuration)
- [Support](#support)

## Overview

These scripts help you:
- Check the status of specific tasks
- Stop stuck retry loops
- Clean up tasks from the result backend
- Monitor worker health and activity
- Revoke problematic tasks

## Prerequisites

- Python environment with access to your Celery app
- `.env` file in the `../backend/` directory with Redis connection details
- Access to your Celery broker (Redis)

## 🚀 Quick Reference

### 🚨 Emergency Commands

```bash
# Stop a stuck retry loop immediately
python stop_retries.py <task_id>

# Check all retrying tasks across system
python stop_retries.py --all-retries

# Force clean up a problematic task
python task_manager.py cleanup <task_id>
```

### 📊 Status Checking

```bash
# Quick status check
python task_manager.py status <task_id>

# Detailed analysis (recommended)
python task_manager.py info <task_id>

# Check if task is retrying
python stop_retries.py --check <task_id>
```

### 🛑 Stopping Tasks

```bash
# Graceful stop
python task_manager.py revoke <task_id>

# Aggressive stop (for stuck retries)
python stop_retries.py <task_id>

# Clean up after stopping
python task_manager.py cleanup <task_id>
```

### 🔍 System Health Check

```bash
# Daily health check routine
python stop_retries.py --all-retries

# If issues found, investigate specific tasks
python task_manager.py info <problematic_task_id>

# Stop problematic tasks
python stop_retries.py <problematic_task_id>
```

### ⚡ Quick Diagnostics

| Symptom | Command | Next Step |
|---------|---------|-----------|
| Task stuck "PENDING" | `python task_manager.py info <task_id>` | If not in queues, cleanup |
| Continuous retry logs | `python stop_retries.py --check <task_id>` | Force stop if retrying |
| System slow/overloaded | `python stop_retries.py --all-retries` | Stop problematic tasks |
| Before deployment | `python stop_retries.py --all-retries` | Clean up first |

### 🎯 Success Indicators

✅ **Task is healthy when:**
- Status shows SUCCESS or expected state
- Not found in retry queues
- No scheduled future executions

❌ **Task needs attention when:**
- Found in scheduled queue repeatedly
- PENDING but not progressing
- Consuming worker resources without progress

## Scripts

### 1. `task_manager.py` - General Task Management

**Purpose**: Comprehensive task management for status checking, revoking, and cleanup.

#### Usage

```bash
# Check basic task status
python task_manager.py status <task_id>

# Get detailed task information (includes worker queue analysis)
python task_manager.py info <task_id>

# Revoke a task (stop it from running)
python task_manager.py revoke <task_id>

# Clean up task from result backend
python task_manager.py cleanup <task_id>
```

#### Examples

```bash
# Check if task is still running
python task_manager.py status 5221e37d-eb39-418c-8abd-0495161caf63

# Get detailed analysis of where task is in the system
python task_manager.py info 5221e37d-eb39-418c-8abd-0495161caf63

# Stop a task and remove it from workers
python task_manager.py revoke 5221e37d-eb39-418c-8abd-0495161caf63

# Clean up task remnants from Redis
python task_manager.py cleanup 5221e37d-eb39-418c-8abd-0495161caf63
```

#### Features

- **Smart Status Detection**: Shows if task is active, reserved, or scheduled
- **Worker Analysis**: Identifies which worker is processing the task
- **Result Backend Integration**: Manages task results in Redis
- **Error Handling**: Graceful handling of connection issues

---

### 2. `stop_retries.py` - Retry Loop Management

**Purpose**: Specialized tool for stopping stuck retry loops and managing retrying tasks.

#### Usage

```bash
# Check if a specific task is stuck in retry loop
python stop_retries.py --check <task_id>

# Force stop a task's retry loop using multiple methods
python stop_retries.py <task_id>

# List all tasks currently scheduled for retry
python stop_retries.py --all-retries
```

#### Examples

```bash
# Check if task is retrying
python stop_retries.py --check 5221e37d-eb39-418c-8abd-0495161caf63

# Aggressively stop all retry attempts
python stop_retries.py 5221e37d-eb39-418c-8abd-0495161caf63

# See all tasks scheduled for retry across all workers
python stop_retries.py --all-retries
```

#### Features

- **Multi-Method Stop**: Uses multiple techniques to ensure task stops
- **Retry Detection**: Identifies tasks in active retry loops
- **Scheduled Task Analysis**: Shows tasks waiting for retry execution
- **Comprehensive Cleanup**: Removes task from all possible locations

---

## Common Scenarios

### Scenario 1: Task Appears Stuck

```bash
# 1. Check what's happening with the task
python task_manager.py info <task_id>

# 2. If it's retrying endlessly
python stop_retries.py --check <task_id>

# 3. Force stop if needed
python stop_retries.py <task_id>
```

### Scenario 2: System Health Check

```bash
# Check for any retrying tasks
python stop_retries.py --all-retries

# If you find problematic tasks, stop them individually
python stop_retries.py <problematic_task_id>
```

### Scenario 3: Clean Shutdown

```bash
# Before maintenance, check what's running
python task_manager.py info <task_id>

# Gracefully stop tasks
python task_manager.py revoke <task_id>

# Clean up afterwards
python task_manager.py cleanup <task_id>
```

## Understanding Task States

### Normal States
- **PENDING**: Task is waiting to be processed or doesn't exist
- **STARTED**: Task has begun execution
- **SUCCESS**: Task completed successfully
- **FAILURE**: Task failed (may or may not retry)

### Problematic States
- **Task in ACTIVE queue**: Currently being processed by a worker
- **Task in RESERVED queue**: Waiting to be picked up by a worker
- **Task in SCHEDULED queue**: Waiting for a future retry attempt

### Queue Locations

| Queue Type | Description | When to Be Concerned |
|------------|-------------|---------------------|
| **Active** | Currently running | If task has been running too long |
| **Reserved** | Waiting to run | If task has been waiting too long |
| **Scheduled** | Future retries | If same task appears repeatedly |

## Troubleshooting Guide

### Issue: Task Shows PENDING but Keeps Retrying

**Symptoms**: Task status is PENDING but you see retry messages in logs

**Solution**:
```bash
python stop_retries.py --check <task_id>
python stop_retries.py <task_id>
```

### Issue: Task Stuck in ACTIVE State

**Symptoms**: Task shows as active but not progressing

**Solution**:
```bash
python task_manager.py info <task_id>
python task_manager.py revoke <task_id>
```

### Issue: Multiple Tasks Retrying

**Symptoms**: System performance degraded due to many retrying tasks

**Solution**:
```bash
python stop_retries.py --all-retries
# Stop each problematic task individually
```

## Script Architecture

### Environment Loading
Both scripts automatically load environment variables from:
- `../backend/.env` file
- Required variables: `BROKER_URL`, `CELERY_RESULT_BACKEND`

### Error Handling
- Graceful connection failure handling
- Clear error messages for troubleshooting
- Safe operation modes (won't accidentally damage working tasks)

### Worker Communication
- Uses Celery's `control.inspect()` for real-time worker data
- Sends control commands to cloud workers
- Handles multiple worker instances

## Best Practices

### Prevention
1. **Set Retry Limits**: Configure `max_retries` in task definitions
2. **Use Exponential Backoff**: Prevent rapid retry storms
3. **Monitor Regularly**: Check `--all-retries` daily
4. **Handle Exceptions**: Don't retry on permanent failures

### Monitoring
1. **Daily Health Check**: Run `python stop_retries.py --all-retries`
2. **Before Deployments**: Check for stuck tasks
3. **After Failures**: Clean up failed tasks promptly

### Emergency Procedures
1. **System Overload**: Stop all retrying tasks immediately
2. **Worker Issues**: Use aggressive cleanup methods
3. **Data Corruption**: Clean result backend for affected tasks

## Configuration

### Required Environment Variables
```bash
# In ../backend/.env
BROKER_URL=rediss://:password@host:port/0?ssl_cert_reqs=CERT_NONE
CELERY_RESULT_BACKEND=rediss://:password@host:port/1?ssl_cert_reqs=CERT_NONE
```

### Optional Enhancements
- Set up monitoring alerts based on retry counts
- Integrate with logging systems for better visibility
- Create automated cleanup jobs for old tasks

## Support

If tasks continue to have issues after using these scripts:
1. Check Redis connectivity
2. Verify worker processes are running
3. Review task code for infinite loops or blocking operations
4. Consider worker restart if problems persist

## Script Files

- `task_manager.py`: General task management (7.2KB, 210 lines)
- `stop_retries.py`: Retry loop management (8.6KB, 241 lines)
- `README.md`: Complete documentation with quick reference (7.0KB, 259+ lines)

All scripts are self-contained and include comprehensive error handling and help messages. 