# Test Execution Modes

This module provides two execution modes for running test configurations:

## Execution Modes

### Sequential Execution
- **File**: `sequential.py`
- **Mode**: `"Sequential"`
- **Behavior**: Tests are executed one after another in sequence
- **Use cases**: Rate-limited endpoints, debugging, endpoints that can't handle concurrent load

### Parallel Execution (Default)
- **File**: `parallel.py`
- **Mode**: `"Parallel"`
- **Behavior**: Tests are executed simultaneously using Celery workers
- **Use cases**: Scalable endpoints, faster execution, independent tests

## Configuration

Set the execution mode in your test configuration's `attributes` property:

```json
{
  "execution_mode": "Sequential"
}
```

Or:

```json
{
  "execution_mode": "Parallel"
}
```

## Module Structure

- **`orchestration.py`**: Main entry point that determines execution mode and delegates
- **`modes.py`**: Utility functions for working with execution modes
- **`parallel.py`**: Parallel execution implementation using Celery chord
- **`sequential.py`**: Sequential execution implementation
- **`shared.py`**: Common utilities shared between execution modes
- **`README.md`**: This documentation file

## Usage Examples

### Programmatic Mode Setting
```python
from rhesis.backend.tasks.execution.modes import set_execution_mode
from rhesis.backend.tasks.enums import ExecutionMode

# Set to sequential mode
success = set_execution_mode(db, test_config_id, ExecutionMode.SEQUENTIAL)

# Set to parallel mode  
success = set_execution_mode(db, test_config_id, ExecutionMode.PARALLEL)
```

### Getting Mode Information
```python
from rhesis.backend.tasks.execution.modes import get_execution_mode, get_mode_description

# Get current mode
mode = get_execution_mode(test_config)

# Get description
description = get_mode_description(mode)
```

## Default Behavior

If no `execution_mode` is specified in the test configuration attributes, the system defaults to **Parallel** execution mode.

## Consistent Results

Both execution modes now produce identical result structures, including:
- **Status tracking**: `status`, `final_status`, `task_state`
- **Progress metrics**: `completed_tests`, `failed_tests`, `total_tests`
- **Timing information**: `started_at`, `completed_at`, `execution_time`
- **Email notifications**: Both modes trigger the same email summary
- **Result processing**: Both use the same `collect_results` task for consistency

## Recommendations

### Use Sequential When:
- Testing endpoints with rate limiting
- Endpoints can't handle concurrent load
- Debugging test execution issues
- Tests have dependencies on each other
- Limited endpoint resources

### Use Parallel When:
- Endpoints can handle concurrent requests
- Tests are independent
- You need faster execution
- Scalable endpoints without rate limits
- High-performance testing scenarios 