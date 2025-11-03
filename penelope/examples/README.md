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

## More Examples Coming Soon

We're working on additional examples covering:

- **Security Testing** - Testing for prompt injection and jailbreaks
- **Compliance Testing** - Verifying GDPR and regulatory compliance
- **Edge Case Discovery** - Finding unusual behaviors
- **Integration with Rhesis Platform** - Using TestSets with Penelope
- **Custom Tools** - Creating and using custom testing tools
- **Batch Testing** - Running multiple tests efficiently

## Contributing Examples

Have an interesting use case? We'd love to see it! Please contribute examples following these guidelines:

1. Clear documentation at the top of the file
2. Well-commented code
3. Realistic, practical scenarios
4. Self-contained (can run independently)

See [CONTRIBUTING.md](../CONTRIBUTING.md) for more details.


