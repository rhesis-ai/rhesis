# Contributing to Rhesis Penelope

Thank you for your interest in contributing to Rhesis Penelope! This document provides guidelines for contributing to the project.

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/rhesis-ai/rhesis.git
cd rhesis/penelope
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

3. Install pre-commit hooks:
```bash
pre-commit install
```

## Development Workflow

### Code Style

We use `ruff` for linting and formatting:

```bash
# Format code
make format

# Check linting
make lint

# Format only changed files
make format_diff
```

### Type Checking

We use `mypy` and `pyright` for type checking:

```bash
make type-check
```

### Testing

Run tests with pytest:

```bash
make test

# Run specific test
pytest tests/test_agent.py

# Run with coverage
pytest --cov=rhesis.penelope
```

### Making Changes

1. Create a new branch for your feature or bugfix:
```bash
git checkout -b feature/your-feature-name
```

2. Make your changes, following these guidelines:
   - Write clear, descriptive commit messages
   - Add tests for new functionality
   - Update documentation as needed
   - Follow existing code style and patterns
   - Add type hints to all functions

3. Run all checks before committing:
```bash
make all
```

4. Push your branch and create a pull request

## Code Guidelines

### Tool Design (Anthropic ACI Principles)

When adding new tools, follow these guidelines:

1. **Extensive Documentation**: Write tool descriptions as if explaining to a junior developer
2. **Clear Examples**: Include good and bad usage examples
3. **Edge Cases**: Document edge cases and limitations
4. **Parameter Design**: Use natural, intuitive parameter names
5. **Error Handling**: Provide clear error messages

Example:
```python
class MyTool(Tool):
    @property
    def description(self) -> str:
        return """
        Brief description.
        
        ═══════════════════════════════════════════
        
        WHEN TO USE:
        ✓ Use case 1
        ✓ Use case 2
        
        WHEN NOT TO USE:
        ✗ Anti-pattern 1
        ✗ Anti-pattern 2
        
        ═══════════════════════════════════════════
        
        EXAMPLES:
        
        Good: example_good
        Bad: example_bad
        """
```

### Agent Behavior

When modifying agent behavior:

1. **Transparency**: Ensure reasoning is visible and logged
2. **Simplicity**: Keep logic simple and composable
3. **Testability**: Make behavior easily testable
4. **Ground Truth**: Use actual endpoint responses for decisions

## Pull Request Process

1. Update README.md with details of changes if applicable
2. Update version numbers following [Semantic Versioning](https://semver.org/)
3. Ensure all tests pass and code is properly formatted
4. Request review from maintainers
5. Address any feedback from reviewers

## Questions?

- Join our [Discord](https://discord.rhesis.ai)
- Open a [Discussion](https://github.com/rhesis-ai/rhesis/discussions)
- Email: engineering@rhesis.ai

## License

By contributing, you agree that your contributions will be licensed under the MIT License.


