# Rhesis

**Testing and validation platform for LLM applications**

Rhesis helps you build reliable AI applications through comprehensive testing, validation, and monitoring.

## Installation

### Basic Installation

```bash
pip install rhesis
```

This installs the core Rhesis SDK with all essential features for testing and validating LLM applications.

### Optional Dependencies

Rhesis supports optional extras for specific use cases. Install them using the bracket syntax:

```bash
pip install rhesis[extra_name]
```

#### Multi-Turn Testing

For conversational AI testing with Penelope (multi-turn testing agent):

```bash
pip install rhesis[penelope]
```

#### Framework Integrations

Install integrations for your preferred LLM framework:

```bash
# LangChain support
pip install rhesis[langchain]

# LangGraph support (includes LangChain)
pip install rhesis[langgraph]

# AutoGen support
pip install rhesis[autogen]
```

#### Advanced Features

```bash
# HuggingFace models for local inference
pip install rhesis[huggingface]

# Garak vulnerability scanner for security testing
pip install rhesis[garak]
```

#### Bundle Options

```bash
# All framework integrations + Penelope
pip install rhesis[all-integrations]

# Everything (all integrations + HuggingFace models)
pip install rhesis[all]
```

#### Combining Extras

You can combine multiple extras:

```bash
pip install rhesis[penelope,langchain]
pip install rhesis[langgraph,garak]
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

## Optional Extras Reference

| Extra | Description | Use Case |
|-------|-------------|----------|
| `penelope` | Multi-turn conversational testing agent | Testing chatbots and conversational AI |
| `langchain` | LangChain integration | Auto-instrumentation for LangChain apps |
| `langgraph` | LangGraph integration | Auto-instrumentation for LangGraph agents |
| `autogen` | AutoGen integration | Auto-instrumentation for AutoGen agents |
| `huggingface` | HuggingFace models support | Local model inference without API calls |
| `garak` | Garak vulnerability scanner | Security and adversarial testing |
| `all-integrations` | All framework integrations + Penelope | Full integration support |
| `all` | Everything | Complete installation with all features |

## Links

- [Website](https://rhesis.ai)
- [GitHub](https://github.com/rhesis-ai/rhesis)
- [PyPI](https://pypi.org/project/rhesis/)

## License

MIT License - see [LICENSE](LICENSE) for details.
