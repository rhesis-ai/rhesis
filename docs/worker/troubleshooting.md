# Worker Troubleshooting Guide

This document covers common issues you may encounter with the Rhesis worker system and how to resolve them.

## Dealing with Stuck Tasks

Sometimes tasks can get stuck in an infinite retry loop, especially chord tasks (`chord_unlock`) when subtasks fail. This can happen if:

1. One or more subtasks in a chord fail permanently
2. The broker connection is interrupted during a chord execution
3. The worker processes are killed unexpectedly

### Symptoms of Stuck Tasks

The most obvious symptom is thousands of repeated log entries like these:

```
Task celery.chord_unlock[82116cfc-ae23-4526-b7ff-7267f389b367] retry: Retry in 1.0s
```

These messages indicate that there are "zombie" tasks that keep retrying indefinitely.

### Configuration to Prevent Stuck Tasks

The worker.py file includes configuration to limit chord retries:

```python
app.conf.update(
    # Other settings...
    
    # Limit chord unlocks to prevent infinite retry loops
    chord_unlock_max_retries=3,
    # Use light amqp result store
    result_persistent=False,
)
```

Additionally, the results handling in `tasks/execution/results.py` includes logic to detect and handle failed subtasks:

```python
# Check for failed tasks and count them
failed_tasks = sum(1 for result in results if result is None)
if failed_tasks > 0:
    logger.warning(f"{failed_tasks} tasks failed out of {total_tests} for test run {test_run_id}")
    
# Determine status based on failures
status = RunStatus.COMPLETED.value
if failed_tasks > 0:
    status = RunStatus.PARTIAL.value if failed_tasks < total_tests else RunStatus.FAILED.value
```

### Purging Stuck Tasks

If you encounter stuck tasks, you can purge all tasks from the queue:

```bash
# Purge all queues (use with caution in production)
celery -A rhesis.backend.worker purge -f
```

This command removes all pending tasks from all queues. Use it with caution in production as it will delete all tasks, including those that are legitimately waiting to be processed.

For a more targeted approach, you can inspect and revoke specific tasks:

```bash
# Inspect active tasks
celery -A rhesis.backend.worker inspect active

# Revoke specific tasks
celery -A rhesis.backend.worker control revoke <task_id>

# Terminate specific tasks (force)
celery -A rhesis.backend.worker control terminate <task_id>
```

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
# Explicitly set tenant context to ensure it's active for all queries
if organization_id:
    # Verify PostgreSQL has the parameter defined
    try:
        db.execute(text('SHOW "app.current_organization"'))
    except Exception as e:
        logger.warning(f"The database parameter 'app.current_organization' may not be defined: {e}")
        # Continue without setting tenant context - will use normal filters instead
    
    # Set the tenant context for this session
    set_tenant(db, organization_id, user_id)
```

## Common Worker Errors

### Error: "chord_unlock" task failing repeatedly

**Symptoms**: Repeated logs of chord_unlock tasks retrying

**Cause**: This typically happens when one or more subtasks in a chord (group of tasks) fail, but the callback still needs to run

**Solution**: 
1. Set a max retry limit for chord_unlock tasks
2. Add proper error handling in the callback function to handle failed subtasks
3. If needed, purge the queue to clear stuck chord_unlock tasks

### Error: No connection to broker

**Symptoms**: Worker fails to start or tasks are not being processed

**Cause**: Connection to the PostgreSQL broker is not working

**Solution**:
1. Check that PostgreSQL is running and accessible
2. Verify that database credentials are correct
3. Ensure that the PostgreSQL extension `pg_trgm` is installed
4. Check firewall rules if running in a cloud environment 