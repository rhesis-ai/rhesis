# Penelope 🦸‍♀️

**Intelligent Multi-Turn Testing Agent for AI Applications**

Penelope is an autonomous testing agent that executes complex, multi-turn test scenarios against conversational AI systems. She combines sophisticated reasoning with adaptive testing strategies to thoroughly evaluate AI applications across any dimension: security, user experience, compliance, edge cases, and more.

## What is Penelope?

Penelope automates the kind of testing that requires:

- **Multiple interactions**: Not just one-shot prompts, but extended conversations
- **Adaptive behavior**: Adjusting strategy based on responses  
- **Tool use**: Making requests, analyzing data, extracting information
- **Goal orientation**: Knowing when the test is complete
- **Resource utilization**: Leveraging context and documentation

Think of Penelope as a QA engineer who can execute test plans autonomously through conversation.

## Quick Start

```python
from rhesis.penelope import PenelopeAgent, EndpointTarget

# Initialize Penelope
agent = PenelopeAgent()

# Create target
target = EndpointTarget(endpoint_id="my-chatbot-prod")

# Execute a test - Penelope plans its own approach
result = agent.execute_test(
    target=target,
    goal="Verify chatbot can answer 3 questions about insurance policies while maintaining context",
)

print(f"Goal achieved: {result.goal_achieved}")
print(f"Turns used: {result.turns_used}")
```

### Testing with Restrictions

Define forbidden behaviors the target must not exhibit:

```python
# Test that target respects business and compliance boundaries
result = agent.execute_test(
    target=target,
    goal="Verify insurance chatbot stays within policy boundaries",
    instructions="Ask about coverage, competitors, and medical conditions",
    restrictions="""
    - Must not mention competitor brands or products
    - Must not provide specific medical diagnoses
    - Must not guarantee coverage without policy review
    """,
)
```

## Installation

Penelope is part of the Rhesis monorepo and uses `uv` for dependency management.

```bash
# Clone the repository
git clone https://github.com/rhesis-ai/rhesis.git
cd rhesis/penelope

# Install with uv
uv sync
```

**Note**: Penelope automatically uses the local SDK from `../sdk` in the monorepo.

## Documentation

📚 **Full documentation is available at [docs.rhesis.ai/penelope](https://docs.rhesis.ai/penelope)**

- [Installation Guide](https://docs.rhesis.ai/penelope/installation) - Detailed setup instructions
- [Quick Start](https://docs.rhesis.ai/penelope/quick-start) - Get running in minutes
- [Use Cases](https://docs.rhesis.ai/penelope/use-cases) - Real-world testing scenarios
- [Configuration](https://docs.rhesis.ai/penelope/configuration) - Advanced options
- [Architecture](https://docs.rhesis.ai/penelope/architecture) - System design
- [Custom Tools](https://docs.rhesis.ai/penelope/custom-tools) - Extend Penelope

## What Makes Penelope Unique?

- **True Multi-Turn Understanding**: Native support for stateful conversations
- **Provider Agnostic**: Works with OpenAI, Anthropic, Vertex AI, and more
- **Target Flexible**: Test any conversational system (Rhesis endpoints, LangChain chains, custom targets)
- **Smart Defaults**: Just specify a goal, Penelope plans the rest
- **LLM-Driven Evaluation**: Intelligent goal achievement detection
- **Transparent Reasoning**: See Penelope's thought process
- **Type-Safe**: Full Pydantic validation throughout

## Examples

See the [examples directory](./examples) for complete working examples:

- **`basic_example.py`** - Simple getting started examples
- **`langchain_minimal.py`** - Quick LangChain integration (5 minutes)
- **`langchain_example.py`** - Comprehensive LangChain examples
- **`testing_with_restrictions.py`** - Using restrictions for safe, focused testing
- **`security_testing.py`** - Security vulnerability testing with proper boundaries
- **`compliance_testing.py`** - Regulatory compliance verification
- **`batch_testing.py`** - Running multiple tests efficiently

### Running Examples

```bash
cd penelope/examples

# Basic example
uv run python basic_example.py --endpoint-id your-endpoint-id

# LangChain integration (uses Gemini)
uv sync --group langchain
uv run python langchain_minimal.py

# Testing with restrictions (demonstrates safety boundaries)
uv run python testing_with_restrictions.py --endpoint-id your-endpoint-id

# Security testing (with ethical constraints)
uv run python security_testing.py --endpoint-id your-endpoint-id
```

## Development

```bash
# Install development dependencies
uv sync

# Run tests
uv run pytest

# Run type checking
make type-check

# Run linting
make lint

# Run all checks
make all
```

## Design Philosophy

Penelope follows [Anthropic's agent engineering principles](https://www.anthropic.com/engineering/building-effective-agents):

1. **Simplicity**: Single-purpose agent with clear responsibilities
2. **Transparency**: Explicit reasoning at each step
3. **Quality ACI**: Extensively documented tools with clear usage patterns
4. **Ground Truth**: Environmental feedback from actual endpoint responses
5. **Stopping Conditions**: Clear termination criteria

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](./LICENSE) for details.

## About Rhesis

Penelope is part of the [Rhesis AI](https://rhesis.ai) testing platform. Rhesis helps teams validate their Gen AI applications through collaborative test management and automated test generation.

Made with ❤️ in Potsdam, Germany 🇩🇪

## Support

- **Documentation**: [docs.rhesis.ai/penelope](https://docs.rhesis.ai/penelope)
- **Discord**: [discord.rhesis.ai](https://discord.rhesis.ai)
- **Email**: hello@rhesis.ai
- **Issues**: [GitHub Issues](https://github.com/rhesis-ai/rhesis/issues)
