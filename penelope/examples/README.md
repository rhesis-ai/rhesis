# Penelope Examples

This directory contains examples demonstrating various use cases for Penelope.

## Prerequisites

**Before running any examples:**

1. **RHESIS_API_KEY**: All examples require a valid Rhesis API key to access endpoints
   - Obtain your API key from [Rhesis App](https://app.rhesis.ai) → Settings
   - Set the environment variable:
     ```bash
     export RHESIS_API_KEY="rh-your-api-key"
     ```
   - 📚 [Full authentication guide](https://docs.rhesis.ai/sdk/installation#configure-the-sdk)

2. **Rhesis Endpoint ID**: The endpoint you want to test
   - Get this from your Rhesis dashboard

## Running Examples

All examples use `uv` and accept command-line arguments:

```bash
# Navigate to the examples directory
cd rhesis/penelope/examples

# Make sure your API key is set
export RHESIS_API_KEY="rh-your-api-key"

# Run with your endpoint ID
uv run python basic_example.py --endpoint-id <your-endpoint-id>

# Or use the short form
uv run python basic_example.py -e <your-endpoint-id>

# Adjust iterations if needed
uv run python basic_example.py -e <your-endpoint-id> --max-iterations 20

# Quiet mode (suppress verbose output)
uv run python basic_example.py -e <your-endpoint-id> --quiet
```

**Command-line options:**
- `--endpoint-id` (or `-e`): Your Rhesis endpoint ID [**required**]
- `--max-iterations`: Maximum number of turns (default: 10)
- `--quiet` (or `-q`): Suppress verbose output
- `--help`: Show help message

## Basic Example

**`basic_example.py`** - Simple multi-turn conversation test

**Demonstrates:**
- Setting up PenelopeAgent with default configuration
- Creating an EndpointTarget
- Defining test instructions and goals
- Executing simple and detailed tests
- Accessing and displaying results
- Viewing conversation history

**Run it:**
```bash
uv run python basic_example.py --endpoint-id <your-endpoint-id>
```

## More Examples

### Security Testing

**`security_testing.py`** - Comprehensive security vulnerability testing

**Demonstrates:**
- Jailbreak resistance testing
- Prompt injection detection
- Information leakage prevention
- Boundary violation checks

⚠️ **Important:** Only test systems you own or have permission to test. Use test/staging environments, never production.

**Run it:**
```bash
uv run python security_testing.py --endpoint-id <your-endpoint-id>
```

### Compliance Testing

**`compliance_testing.py`** - Regulatory compliance verification

**Demonstrates:**
- GDPR compliance testing
- PII handling verification
- Age restrictions (COPPA) checking
- Accessibility standards validation
- Content moderation policy testing

**Run it:**
```bash
uv run python compliance_testing.py --endpoint-id <your-endpoint-id>
```

### Edge Case Discovery

**`edge_case_discovery.py`** - Finding unusual behaviors and boundaries

**Demonstrates:**
- Input variation testing (empty, long, special chars)
- Multi-language support checking
- Ambiguous input handling
- Error recovery testing
- Boundary value testing
- Rapid context switching

**Run it:**
```bash
uv run python edge_case_discovery.py --endpoint-id <your-endpoint-id>
```

### Platform Integration

**`platform_integration.py`** - Rhesis platform integration

**Demonstrates:**
- Loading TestSets from Rhesis platform
- Executing tests from platform
- Storing results back to platform
- Batch execution of multiple test sets

📝 **Note:** Requires valid TestSet IDs in your Rhesis platform account.

**Run it:**
```bash
uv run python platform_integration.py --endpoint-id <your-endpoint-id>
```

### Custom Tools

**`custom_tools.py`** - Creating custom testing tools

**Demonstrates:**
- Database verification tool implementation
- API monitoring tool
- Security scanner tool
- Tool registration with Penelope agent
- Using custom tools in tests

**Run it:**
```bash
uv run python custom_tools.py --endpoint-id <your-endpoint-id>
```

### Batch Testing

**`batch_testing.py`** - Running multiple tests efficiently

**Demonstrates:**
- Batch test execution
- Result aggregation and analysis
- Test report generation
- Exporting results to JSON
- Category-specific testing
- Parallel testing concepts

**Run it:**
```bash
uv run python batch_testing.py --endpoint-id <your-endpoint-id>
```

## Contributing Examples

Have an interesting use case? We'd love to see it! Please contribute examples following these guidelines:

1. Clear documentation at the top of the file
2. Well-commented code
3. Realistic, practical scenarios
4. Self-contained (can run independently)

See [CONTRIBUTING.md](../CONTRIBUTING.md) for more details.


