# SDK-SPEC-0001 — AgentOBS Python SDK Specification

**Reference Implementation for the SpanForge Observability Standard**

| Field | Value |
|---|---|
| Document ID | SDK-SPEC-0001 |
| Version | 0.1 Draft |
| Date | March 4, 2026 |
| Status | Draft |
| Supersedes | — |
| Related | RFC-0001-AGENTOBS |

---

## 1. Purpose

AgentOBS is the official Python reference SDK for the SpanForge Observability Standard.

The SDK provides:

- A developer-friendly instrumentation API
- Full SpanForge schema compliance
- Built-in observability exporters
- Provider normalization for LLM APIs

### 1.1 MUST requirements

The SDK MUST:

- Generate valid SpanForge events
- Implement the event schema
- Simplify AI observability instrumentation

### 1.2 Priority order

The SDK MUST prioritize (in order):

1. Developer experience
2. Standards compliance
3. Minimal dependencies
4. Production safety

---

## 2. Design Principles

### P1 — Simple Developer API

Instrumentation MUST be possible in ≤5 lines of code.

```python
from agentobs import tracer

with tracer.span("chat", model="gpt-4o"):
    response = client.chat(...)
```

The SDK MUST automatically generate:

- Event envelope
- ULID
- Timestamps
- Span hierarchy
- Token usage
- Cost breakdown (if available)

### P2 — SpanForge Compliance

All events emitted by AgentOBS MUST conform to the SpanForge standard. This includes:

- Event envelope
- Namespace taxonomy
- Payload structure
- Canonical JSON serialization

### P3 — Minimal Dependencies

The core SDK MUST depend only on the Python standard library.

Optional integrations MAY introduce dependencies.

```
pip install agentobs           # core only — stdlib dependencies
pip install agentobs[otlp]     # + opentelemetry-exporter-otlp
pip install agentobs[openai]   # + openai HTTP response parsing
pip install agentobs[datadog]  # + datadog agent client
```

### P4 — Deterministic Serialization

All event serialization MUST produce canonical JSON as defined by the SpanForge standard:

- Keys sorted alphabetically
- Null fields omitted
- Compact separators `(",", ":")`

### P5 — Safe Defaults

AgentOBS MUST:

- Auto-generate ULIDs
- Auto-create spans
- Auto-close spans on context exit
- Validate event schema on emit

---

## 3. Package Name

**Official Python package name:** `agentobs`

```
pip install agentobs
```

**Import root:** `agentobs`

**Previous name:** `llm_toolkit_schema` (superseded)

---

## 4. Public API

The SDK MUST expose a minimal top-level API.

### Primary interface

```python
from agentobs import tracer
from agentobs import configure
```

### Optional

```python
from agentobs import span
```

---

## 5. Configuration API

Global configuration function; MUST be called before any spans are created.

```python
configure(
    exporter="jsonl",
    endpoint=None,
    org_id=None,
    service_name=None,
    env="production"
)
```

### Supported exporters

| Exporter key | Purpose |
|---|---|
| `jsonl` | Local file export to `agentobs_events.jsonl` |
| `console` | Pretty-print for development and debugging |
| `webhook` | HTTP POST delivery to external endpoints |
| `otlp` | Export to OpenTelemetry collectors |
| `datadog` | Datadog observability platform |
| `grafana_loki` | Grafana Loki log aggregation |

### Configuration precedence

Environment variables MUST override defaults and MAY supplement `configure()` kwargs:

| Env var | Maps to |
|---|---|
| `AGENTOBS_EXPORTER` | `exporter` |
| `AGENTOBS_ENDPOINT` | `endpoint` |
| `AGENTOBS_ORG_ID` | `org_id` |
| `AGENTOBS_SERVICE_NAME` | `service_name` |
| `AGENTOBS_ENV` | `env` |

---

## 6. Tracer Interface

The `tracer` object manages span creation and is a module-level singleton.

```python
from agentobs import tracer

with tracer.span("chat", model="gpt-4o"):
    ...
```

### `tracer.span()` signature

```python
tracer.span(
    name: str,
    model: str | None = None,
    operation: str = "chat",
    attributes: dict | None = None
) -> SpanContextManager
```

### Return type

Returns a `SpanContextManager` that:

- Enters by creating and starting a `Span`
- Exits by recording duration and emitting the `SpanPayload` event
- Propagates exceptions as error status on the span

---

## 7. Span Object

A `Span` represents a single trace unit within a run.

### Supported operations

```python
span.set_attribute(key: str, value: Any) -> None
span.record_error(exception: Exception) -> None
span.end() -> None
```

### Example

```python
with tracer.span("chat") as span:
    span.set_attribute("temperature", 0.7)
    span.set_attribute("system_prompt_length", 512)
```

---

## 8. Automatic Span Population

AgentOBS MUST automatically populate these fields on every span:

| Field | Source |
|---|---|
| `trace_id` | Generated ULID (per trace, stable across sibling spans) |
| `span_id` | Generated ULID (unique per span) |
| `event_id` | Generated ULID |
| `timestamp` | System clock (ISO 8601, microsecond precision, UTC) |
| `schema_version` | `"2.0"` |
| `source` | `service_name@version` from config |

---

## 9. Event Creation

On span completion, AgentOBS MUST emit an event of type:

```
llm.trace.span.completed
```

The payload MUST match `SpanPayload` as defined in the SpanForge standard (RFC-0001-AGENTOBS §8.1).

---

## 10. Agent Instrumentation

AgentOBS MUST support nested agent workflows via:

```python
tracer.agent_run(name: str, ...) -> AgentRunContextManager
tracer.agent_step(name: str, ...) -> AgentStepContextManager
```

### Example

```python
with tracer.agent_run("research_agent"):

    with tracer.agent_step("search"):
        ...

    with tracer.agent_step("summarize"):
        ...
```

### Events emitted

| Event | Trigger |
|---|---|
| `llm.trace.agent.step` | On `agent_step` context exit |
| `llm.trace.agent.completed` | On `agent_run` context exit |

Payloads MUST match `AgentStepPayload` and `AgentRunPayload` respectively.

---

## 11. Provider Integrations

The SDK SHOULD provide built-in provider integrations as optional extras.

### Supported providers

| Provider | Install extra |
|---|---|
| OpenAI | `agentobs[openai]` |
| Anthropic | `agentobs[anthropic]` *(planned)* |
| Ollama | `agentobs[ollama]` *(planned)* |
| Groq | `agentobs[groq]` *(planned)* |
| Together AI | `agentobs[together]` *(planned)* |

### Usage

```python
from agentobs.integrations import openai
```

### Integration contract

Integrations MUST automatically extract:

- Model name → `ModelInfo.name`
- Token usage → `TokenUsage` (normalized)
- Cost information → `CostBreakdown` (or zero-value if unavailable)

---

## 12. Token Normalization

All provider responses MUST be normalized into the standard `TokenUsage` value object.

```python
@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    image_tokens: int = 0
```

Provider-specific field names (e.g. `prompt_tokens`, `completion_tokens`) MUST be mapped to `input_tokens` / `output_tokens` during normalization.

---

## 13. Cost Calculation

If pricing data is available, the SDK MUST generate a populated `CostBreakdown`.

If pricing data is unavailable:

- MUST use `0.0` values
- MUST still produce a valid `CostBreakdown` schema object (never `None`)

```python
@dataclass
class CostBreakdown:
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    cached_cost_usd: float = 0.0
    reasoning_cost_usd: float = 0.0
```

---

## 14. Exporters

All exporters MUST implement the `Exporter` protocol:

```python
class Exporter(Protocol):
    def export(self, events: list[Event]) -> None: ...
```

### Built-in exporters

#### JSONLExporter

Writes newline-delimited JSON events to a file.

- Default file: `agentobs_events.jsonl`
- Configurable via `endpoint` parameter

#### ConsoleExporter

Pretty-prints events to stdout for development use.

#### OTLPExporter

Exports events to an OpenTelemetry-compatible collector.

- Requires `agentobs[otlp]`

#### WebhookExporter

HTTP POSTs events as JSON to a configured endpoint.

- Configurable via `endpoint` parameter

---

## 15. EventStream

The SDK MUST maintain an internal `EventStream` buffer with the following capabilities:

- Filtering events by type or namespace
- Batch exporting to one or more exporters
- Routing events to different exporters based on event type

---

## 16. ULID Generation

AgentOBS MUST implement ULID generation using Crockford Base32 encoding.

Requirements:

- MUST ensure monotonic ordering within the same millisecond
- MUST comply with RFC-0001 §6.3 first-character constraint (`[0-7]`)
- MUST NOT require external dependencies for ULID generation

---

## 17. Canonical JSON

Event serialization MUST:

- Sort all keys alphabetically
- Omit null / `None` fields
- Use compact separators `(",", ":")`

Primary method:

```python
event.to_json() -> str
```

---

## 18. Security Profile *(Optional)*

Security features SHOULD be available as opt-in:

```python
sign_event(event: Event, key: bytes) -> Event
verify_chain(events: list[Event], key: bytes) -> ChainVerificationResult
```

Algorithm: **HMAC-SHA256**

Signing MUST occur after payload construction and before export.

---

## 19. Privacy Profile *(Optional)*

The privacy module MUST support:

```python
class Redactable:
    ...

class RedactionPolicy:
    ...
```

Redaction MUST occur **before** event export, never after.

Supported sensitivity levels: `LOW`, `MEDIUM`, `HIGH`, `PII`, `PHI`

---

## 20. CLI Tool

AgentOBS SHOULD provide a CLI entry point.

```
agentobs check-compat events.jsonl
agentobs validate events.jsonl
agentobs audit-chain events.jsonl
```

| Command | Function |
|---|---|
| `check-compat` | Validate schema compatibility of a JSONL event file |
| `validate` | Strict schema validation against SpanForge standard |
| `audit-chain` | Verify HMAC audit chain integrity |

---

## 21. Framework Integrations

The SDK SHOULD provide integrations for:

| Framework | Module |
|---|---|
| OpenTelemetry | `agentobs.integrations.otel` |
| FastAPI | `agentobs.integrations.fastapi` |
| LangChain | `agentobs.integrations.langchain` |
| LangGraph | `agentobs.integrations.langgraph` |
| CrewAI | `agentobs.integrations.crewai` |

---

## 22. Minimal Example

```python
from agentobs import tracer, configure

configure(exporter="jsonl")

with tracer.span("chat", model="gpt-4o"):
    response = client.chat(...)
```

The generated event MUST be compliant with the SpanForge standard.

---

## 23. Agent Workflow Example

```python
from agentobs import tracer, configure

configure(exporter="jsonl", service_name="research-service")

with tracer.agent_run("research_agent"):

    with tracer.agent_step("search"):
        results = search_tool.run(query)

    with tracer.agent_step("summarize"):
        summary = llm.summarize(results)
```

---

## 24. Versioning

AgentOBS MUST follow [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).

- Initial production release: `1.0.0`
- Pre-release series: `0.x.y`
- Breaking changes increment MAJOR

---

## 25. Reference Implementation

AgentOBS is the reference implementation of the SpanForge Observability Standard.

SDKs in other languages SHOULD follow the same API design patterns and field naming conventions defined in this document.

---

## 26. Success Criteria

AgentOBS will be considered production-ready (`1.0.0`) when all of the following are met:

| Criterion | Target |
|---|---|
| SpanForge compliance verified | 100% of emitted events pass schema validation |
| Exporters | ≥3 built-in exporters implemented and tested |
| Provider integrations | ≥3 provider integrations available |
| Agent instrumentation | `agent_run` + `agent_step` fully operational |
| Example applications | ≥2 runnable example apps published |
| Test coverage | ≥90% line coverage on core SDK |
| Documentation | Full API reference + quickstart guide |

---

*End of SDK-SPEC-0001 v0.1 Draft*
