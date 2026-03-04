# Installation

## Requirements

- Python **3.9** or later
- No required third-party dependencies for core event creation

## Install from PyPI

```bash
pip install tracium
```

## Optional extras

| Extra | Install command | What it enables |
|-------|-----------------|----------------|
| `jsonschema` | `pip install "tracium[jsonschema]"` | `validate_event` with full JSON Schema validation |
| `http` | `pip install "tracium[http]"` | `OTLPExporter` and `WebhookExporter` (stdlib transport; reserved for future `httpx` upgrade) |
| `pydantic` | `pip install "tracium[pydantic]"` | `tracium.models` — Pydantic v2 model layer, `model_json_schema()` |
| `otel` | `pip install "tracium[otel]"` | `OTelBridgeExporter` — emits events through any configured `TracerProvider` (`opentelemetry-sdk>=1.24`) |
| `kafka` | `pip install "tracium[kafka]"` | `EventStream.from_kafka()` via `kafka-python>=2.0` |
| `langchain` | `pip install "tracium[langchain]"` | `LLMSchemaCallbackHandler` via `langchain-core>=0.2` |
| `llamaindex` | `pip install "tracium[llamaindex]"` | `LLMSchemaEventHandler` via `llama-index-core>=0.10` |
| `datadog` | `pip install "tracium[datadog]"` | `DatadogExporter` (stdlib transport; reserved for future `ddtrace` integration) |
| `all` | `pip install "tracium[all]"` | All optional extras |

Install all optional extras at once:

```bash
pip install "tracium[all]"
```

## Development installation

```bash
git clone https://github.com/llm-toolkit/tracium.git
cd tracium
python -m venv .venv
.venv/Scripts/activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -e ".[dev]"
```

This installs all development dependencies including pytest, ruff, mypy, and
all optional extras.

## Verify the installation

```python
import tracium
print(tracium.__version__)   # 0.1.0
print(tracium.SCHEMA_VERSION)  # 2.0

from tracium import Event, EventType
evt = Event(
    event_type=EventType.TRACE_SPAN_COMPLETED,
    source="smoke-test@1.0.0",
    payload={"ok": True},
)
evt.validate()
print("Installation OK")
```
