# CI/CD Integration Examples

Complete examples for integrating Rhesis SDK into your CI/CD pipeline.

## Files

- **`rhesis-tests.yml`** - GitHub Actions workflow file
- **`run_rhesis_tests.py`** - Python test runner script

## Quick Start

1. Copy `rhesis-tests.yml` to `.github/workflows/rhesis-tests.yml` in your repository
2. Copy `run_rhesis_tests.py` to `.github/scripts/run_rhesis_tests.py` in your repository
3. Configure secrets in your CI/CD platform (see [CI/CD Integration Guide](/guides/ci-cd-integration))

## Customization

### Adjust Workflow Triggers

Edit the `on:` section in `rhesis-tests.yml` to trigger on different events:

```yaml
on:
  pull_request:
    branches: [main]
    types: [opened, synchronize, reopened]
```

### Modify Timeouts

Edit timeout values in `run_rhesis_tests.py`:

```python
# Poll for test run (default: 600s / 10 minutes)
test_run_id = poll_for_test_run(test_configuration_id, timeout=900)

# Wait for completion (default: 1800s / 30 minutes)
wait_for_completion(test_run, timeout=3600)
```

### Set Failure Threshold

Modify the failure check in `run_rhesis_tests.py` to allow a percentage of failures:

```python
# Allow up to 5% failure rate
failure_threshold = 0.05
failure_rate = summary["failed"] / summary["total"]

if failure_rate > failure_threshold:
    print(f"❌ Failure rate {failure_rate:.1%} exceeds threshold {failure_threshold:.1%}")
    sys.exit(1)
```

## Documentation

For detailed setup instructions, see the [CI/CD Integration Guide](/guides/ci-cd-integration).

