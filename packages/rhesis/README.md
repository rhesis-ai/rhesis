# Rhesis

**Testing and validation platform for LLM applications**

`rhesis` is the lightweight Rhesis package. It ships `rhesis.telemetry`: the tracing primitives
(semantic-convention attributes, conversation context, token extraction, the OTLP exporter and
tracer provider) shared by the SDK and its framework integrations. Pick an extra:

| Install | What you get |
|---|---|
| `pip install "rhesis[telemetry]"` | `rhesis.telemetry` with its OpenTelemetry dependencies, for sending traces to Rhesis without the full SDK |
| `pip install "rhesis[sdk]"` | The full [`rhesis-sdk`](https://pypi.org/project/rhesis-sdk/) |
| `pip install "rhesis[all]"` | Both |

`rhesis.telemetry` needs the `telemetry` extra (or the SDK, which brings OpenTelemetry with it) to
import.

## Usage

Tracing without the SDK (`rhesis[telemetry]`):

```python
from rhesis.telemetry import build_tracer_provider

provider = build_tracer_provider(
    service_name="my-app",
    api_key="rh-...",
    base_url="https://api.rhesis.ai",
    project_id="your-project-id",
    environment="development",
)
```

With the full SDK (`rhesis[sdk]`):

```python
from rhesis.sdk import RhesisClient

client = RhesisClient()
```

## Documentation

- **Full Documentation**: [docs.rhesis.ai](https://docs.rhesis.ai)
- **API Reference**: [docs.rhesis.ai/api](https://docs.rhesis.ai/api)
- **Getting Started Guide**: [docs.rhesis.ai/getting-started](https://docs.rhesis.ai/getting-started)

## Links

- [Website](https://rhesis.ai)
- [GitHub](https://github.com/rhesis-ai/rhesis)
- [PyPI - rhesis](https://pypi.org/project/rhesis/)
- [PyPI - rhesis-sdk](https://pypi.org/project/rhesis-sdk/)

## License

MIT License - see [LICENSE](LICENSE) for details.
