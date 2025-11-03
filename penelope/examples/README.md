# Penelope Examples

This directory contains examples demonstrating various use cases for Penelope.

## Running Examples

All examples use `uv` to run with the proper dependencies:

```bash
# Make sure you're in the penelope directory
cd rhesis/penelope

# Edit the example file to configure your endpoint_id
# Then run with uv:
cd examples
uv run python basic_example.py
```

## Basic Example

**`basic_example.py`** - Simple multi-turn conversation test

Demonstrates:
- Setting up PenelopeAgent with default configuration
- Creating an EndpointTarget
- Defining test instructions and goals
- Executing simple and detailed tests
- Accessing and displaying results
- Viewing conversation history

**Prerequisites:**
- Penelope installed (see [Installation](../README.md#installation))
- Valid Rhesis endpoint configured
- Set your `endpoint_id` in the example file

**Run it:**
```bash
# Edit basic_example.py to set your endpoint_id
# Then run:
uv run python basic_example.py
```

## More Examples

### Security Testing

**`security_testing.py`** - Comprehensive security vulnerability testing

Demonstrates:
- Jailbreak resistance testing
- Prompt injection detection
- Information leakage prevention
- Boundary violation checks

**Prerequisites:**
- Test/staging environment (never test production without permission)
- Valid endpoint configured
- Proper authorization for security testing

**Run it:**
```bash
uv run python security_testing.py
```

### Compliance Testing

**`compliance_testing.py`** - Regulatory compliance verification

Demonstrates:
- GDPR compliance testing
- PII handling verification
- Age restrictions (COPPA) checking
- Accessibility standards validation
- Content moderation policy testing

**Run it:**
```bash
uv run python compliance_testing.py
```

### Edge Case Discovery

**`edge_case_discovery.py`** - Finding unusual behaviors and boundaries

Demonstrates:
- Input variation testing (empty, long, special chars)
- Multi-language support checking
- Ambiguous input handling
- Error recovery testing
- Boundary value testing
- Rapid context switching

**Run it:**
```bash
uv run python edge_case_discovery.py
```

### Platform Integration

**`platform_integration.py`** - Rhesis platform integration

Demonstrates:
- Loading TestSets from Rhesis platform
- Executing tests from platform
- Storing results back to platform
- Batch execution of multiple test sets

**Prerequisites:**
- RHESIS_API_KEY environment variable set
- Valid TestSet IDs in Rhesis platform

**Run it:**
```bash
export RHESIS_API_KEY='your-api-key'
uv run python platform_integration.py
```

### Custom Tools

**`custom_tools.py`** - Creating custom testing tools

Demonstrates:
- Database verification tool implementation
- API monitoring tool
- Security scanner tool
- Tool registration with Penelope agent
- Using custom tools in tests

**Run it:**
```bash
uv run python custom_tools.py
```

### Batch Testing

**`batch_testing.py`** - Running multiple tests efficiently

Demonstrates:
- Batch test execution
- Result aggregation and analysis
- Test report generation
- Exporting results to JSON
- Category-specific testing
- Parallel testing concepts

**Run it:**
```bash
uv run python batch_testing.py
```

## Contributing Examples

Have an interesting use case? We'd love to see it! Please contribute examples following these guidelines:

1. Clear documentation at the top of the file
2. Well-commented code
3. Realistic, practical scenarios
4. Self-contained (can run independently)

See [CONTRIBUTING.md](../CONTRIBUTING.md) for more details.


