# Rhesis

**Testing and validation platform for LLM applications**

Rhesis helps you build reliable AI applications through comprehensive testing, validation, and monitoring.

## Installation

```bash
pip install rhesis
```

This installs the full Rhesis SDK. For additional features:

```bash
# Multi-turn testing agent
pip install rhesis[penelope]

# Framework integrations
pip install rhesis[langchain]
pip install rhesis[langgraph]

# Everything
pip install rhesis[all]
```

## Quick Start

```python
from rhesis.sdk import RhesisClient

client = RhesisClient()
```

## Documentation

- **Full Documentation**: [docs.rhesis.ai](https://docs.rhesis.ai)
- **API Reference**: [docs.rhesis.ai/api](https://docs.rhesis.ai/api)
- **Getting Started Guide**: [docs.rhesis.ai/getting-started](https://docs.rhesis.ai/getting-started)

## Packages

The Rhesis ecosystem includes:

| Package | Description |
|---------|-------------|
| `rhesis` | Umbrella package (this package) - installs rhesis-sdk |
| `rhesis-sdk` | Core SDK for testing and validation |
| `rhesis-penelope` | Multi-turn testing agent |

## Optional Extras

| Extra | Description |
|-------|-------------|
| `penelope` | Multi-turn conversational testing agent |
| `langchain` | LangChain integration |
| `langgraph` | LangGraph integration |
| `autogen` | AutoGen integration |
| `huggingface` | HuggingFace models support |
| `garak` | Garak vulnerability scanner |
| `all-integrations` | All framework integrations + Penelope |
| `all` | Everything including HuggingFace models |

## Links

- [Website](https://rhesis.ai)
- [GitHub](https://github.com/rhesis-ai/rhesis)
- [PyPI](https://pypi.org/project/rhesis/)

## License

MIT License - see [LICENSE](LICENSE) for details.
