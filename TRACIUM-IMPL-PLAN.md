# Tracium SDK — Phased Implementation Plan

**Document:** SDK-IMPL-0001
**Spec reference:** SDK-SPEC-0001 v0.1
**Schema reference:** RFC-0001-AGENTOBS v2.0
**Date:** March 4, 2026
**Status:** Active

---

## Baseline State

The repository currently contains a fully compliant `llm_toolkit_schema` Python package at schema version `2.0.0`. All 36 event types, 42 namespace payload classes, and 11 namespace modules are implemented and import-verified. This is the foundation we build Tracium on top of — nothing here gets deleted, only extended and re-packaged.

---

## Phase Overview

| Phase | Name | Goal | Output |
|---|---|---|---|
| 0 | **Package Rename** | Rename `llm_toolkit_schema` → `tracium`; update all references | `tracium/` importable, backward compat alias |
| 1 | **Configuration Layer** | `configure()` API, env var support, global config singleton | `tracium.configure()` |
| 2 | **Core Tracer + Span** | `tracer.span()`, `SpanContextManager`, auto-population | `from tracium import tracer` works end-to-end |
| 3 | **Event Emission** | Span close → `Event` → `EventStream` → exporter | Events written to JSONL on span exit |
| 4 | **Agent Instrumentation** | `tracer.agent_run()`, `tracer.agent_step()`, nesting | Nested agent events emitted correctly |
| 5 | **ConsoleExporter** | Human-readable dev output (`exporter="console"`) | Pretty-print on span exit |
| 6 | **OpenAI Integration** | Auto-extract tokens + model from OpenAI response | `from tracium.integrations import openai` |
| 7 | **Additional Provider Integrations** | Anthropic, Ollama, Groq, Together AI | 4 more provider normalizers |
| 8 | **Additional Exporters** | OTLP, Webhook, Datadog, Grafana Loki | All 6 exporters from spec §5 |
| 9 | **Framework Integrations** | FastAPI, LangChain, LangGraph, CrewAI | `tracium.integrations.*` modules |
| 10 | **CLI Tooling** | `tracium check-compat`, `validate`, `audit-chain` | `tracium` command available after install |
| 11 | **Security + Privacy** | `sign_event()`, `verify_chain()`, `Redactable` wiring | Opt-in HMAC + PII redaction before export |
| 12 | **Hardening + Docs** | Test coverage ≥90%, API reference, examples, `1.0.0` | Production release |

---

## Phase 0 — Package Rename

**Goal:** Rename the package from `llm_toolkit_schema` to `tracium` with a backward-compatibility shim.

### Tasks

1. **Rename the package directory**
   - `llm_toolkit_schema/` → `tracium/`
   - Update all `from llm_toolkit_schema import` → `from tracium import` inside the package

2. **Update `pyproject.toml`**
   - `name = "tracium"`
   - `version = "0.1.0"`
   - Update `[project.entry-points]` for CLI
   - Update package discovery: `packages = ["tracium", "tracium.*"]`

3. **Add backward-compatibility shim**
   Create `llm_toolkit_schema/` as a shim package:
   ```python
   # llm_toolkit_schema/__init__.py (shim)
   import warnings
   warnings.warn(
       "llm_toolkit_schema is deprecated; use tracium instead.",
       DeprecationWarning, stacklevel=2
   )
   from tracium import *  # noqa: F401, F403
   from tracium import __all__  # noqa: F401
   ```

4. **Update `README.md`, `RELEASE.md`, doc references**

5. **Verify import parity**
   ```
   python -c "import tracium; print(tracium.__version__)"
   python -c "import llm_toolkit_schema"  # deprecation warning, not error
   ```

### Files changed

```
llm_toolkit_schema/         → tracium/
llm_toolkit_schema/__init__ → shim only
pyproject.toml              name, version, packages
README.md                   install instructions
docs/conf.py                project name
```

### Acceptance criteria

- `import tracium` succeeds
- `import llm_toolkit_schema` emits `DeprecationWarning` but does not raise
- All 42 namespace payload classes reachable via `tracium.*`
- `tracium.__version__ == "0.1.0"`

---

## Phase 1 — Configuration Layer

**Goal:** Implement `configure()` and the global config singleton backing all tracer behaviour.

### New file: `tracium/config.py`

```python
@dataclass
class TraciumConfig:
    exporter: str = "console"
    endpoint: str | None = None
    org_id: str | None = None
    service_name: str = "unknown-service"
    env: str = "production"
    # derived
    service_version: str = "0.0.0"
```

- Read from env vars at import time (see §5 of spec)
- `configure(**kwargs)` merges kwargs into singleton, then re-initialises the active exporter
- Thread-safe using `threading.Lock`

### Env var mapping

| Env var | Field |
|---|---|
| `TRACIUM_EXPORTER` | `exporter` |
| `TRACIUM_ENDPOINT` | `endpoint` |
| `TRACIUM_ORG_ID` | `org_id` |
| `TRACIUM_SERVICE_NAME` | `service_name` |
| `TRACIUM_ENV` | `env` |

### Update `tracium/__init__.py`

```python
from tracium.config import configure
```

### Acceptance criteria

- `configure(exporter="jsonl", service_name="my-svc")` mutates the singleton
- `TRACIUM_EXPORTER=console python -c "from tracium import tracer"` picks up env var
- `configure()` is idempotent (calling twice with same args is safe)

---

## Phase 2 — Core Tracer + Span

**Goal:** `tracer.span()` is a working context manager that auto-populates all required fields.

### New files

```
tracium/
    _tracer.py       # Tracer class + module-level `tracer` singleton
    _span.py         # Span + SpanContextManager
```

### `tracium/_span.py`

```python
@dataclass
class Span:
    name: str
    span_id: str          # ULID, generated on __enter__
    trace_id: str         # ULID, inherited from parent or generated
    parent_span_id: str | None
    model: str | None
    operation: str
    attributes: dict
    start_time: str       # ISO 8601 microseconds UTC
    end_time: str | None
    duration_ms: float | None
    status: str           # "ok" | "error"
    error_message: str | None

    def set_attribute(self, key: str, value) -> None: ...
    def record_error(self, exc: Exception) -> None: ...
    def end(self) -> None: ...
```

### `SpanContextManager`

- `__enter__` → creates `Span`, pushes to thread-local stack
- `__exit__` → calls `span.end()`, pops stack, triggers event emission

### `tracium/_tracer.py`

```python
class Tracer:
    def span(self, name, model=None, operation="chat", attributes=None) -> SpanContextManager: ...
    def agent_run(self, name, ...) -> AgentRunContextManager: ...  # Phase 4
    def agent_step(self, name, ...) -> AgentStepContextManager: ... # Phase 4

tracer = Tracer()  # module-level singleton
```

### Auto-population (spec §8)

On every span, Tracium MUST auto-assign:

| Field | Source |
|---|---|
| `span_id` | `generate_ulid()` |
| `trace_id` | Inherited from parent span on stack, else `generate_ulid()` |
| `event_id` | `generate_ulid()` |
| `timestamp` | `datetime.utcnow().isoformat(timespec="microseconds") + "Z"` |
| `schema_version` | `"2.0"` |
| `source` | `f"{config.service_name}@{config.service_version}"` |

### Update `tracium/__init__.py`

```python
from tracium._tracer import tracer
```

### Acceptance criteria

```python
from tracium import tracer, configure
configure(exporter="console")
with tracer.span("test", model="gpt-4o") as s:
    s.set_attribute("test_key", "test_value")
# → span completes, no exceptions
```

---

## Phase 3 — Event Emission

**Goal:** Span close emits a valid `SpanPayload` event through the `EventStream` to the configured exporter.

### Flow

```
Span.__exit__
  → build SpanPayload (from span fields)
  → build Event(event_type=EventType.TRACE_SPAN_COMPLETED, payload=span_payload.to_dict())
  → Event.validate()
  → EventStream.emit(event)
  → Exporter.export([event])
```

### New file: `tracium/_stream.py`

- Wraps existing `EventStream` from the schema package
- Holds reference to active `Exporter` from config
- `emit(event)` → calls exporter immediately (batch support in Phase 8)

### New file: `tracium/exporters/jsonl.py`

- Wraps `JSONLExporter` from `tracium.export`
- Default output file: `tracium_events.jsonl`
- Configurable via `endpoint` config field

### Acceptance criteria

```python
configure(exporter="jsonl", endpoint="./my_events.jsonl")
with tracer.span("chat", model="gpt-4o"):
    pass
# → my_events.jsonl contains one valid JSON line
# → Event passes schema validation
import json
line = open("my_events.jsonl").readline()
event_data = json.loads(line)
assert event_data["event_type"] == "llm.trace.span.completed"
assert event_data["schema_version"] == "2.0"
```

---

## Phase 4 — Agent Instrumentation

**Goal:** `tracer.agent_run()` and `tracer.agent_step()` work as nested context managers, emitting correct payloads.

### API

```python
with tracer.agent_run("research_agent") as run:
    with tracer.agent_step("search") as step:
        step.set_attribute("query", "what is RAG?")
    with tracer.agent_step("summarize"):
        ...
```

### Events emitted

| Context | Event type | Payload |
|---|---|---|
| `agent_step.__exit__` | `llm.trace.agent.step` | `AgentStepPayload` |
| `agent_run.__exit__` | `llm.trace.agent.completed` | `AgentRunPayload` |

### `AgentRunContextManager`

- On enter: create `agent_run_id` ULID, push to thread-local run stack
- On exit: collect all child step events, emit `AgentRunPayload` with aggregated stats (total tokens, total cost, step count, duration)

### `AgentStepContextManager`

- On enter: inherit `trace_id` and `agent_run_id` from parent run context
- On exit: emit `AgentStepPayload`

### Acceptance criteria

```python
configure(exporter="jsonl")
with tracer.agent_run("test_agent"):
    with tracer.agent_step("step_1"):
        pass
# → 2 events in JSONL: agent.step + agent.completed
# → AgentStepPayload.agent_run_id == AgentRunPayload.agent_run_id
```

---

## Phase 5 — ConsoleExporter

**Goal:** Provide a human-readable development exporter usable with `configure(exporter="console")`.

### New file: `tracium/exporters/console.py`

Output format:
```
╔══ span: chat [gpt-4o] ══════════════════════════════╗
║  event_id   : 01JXXXXXXXXXXXXXXXXXXXXXXX
║  trace_id   : 01JXXXXXXXXXXXXXXXXXXXXXXX
║  duration   : 142.3ms
║  tokens     : in=512  out=128  total=640
║  cost        : $0.00096
║  status     : ok
╚═════════════════════════════════════════════════════╝
```

- Uses only `sys.stdout` and ANSI escape codes (stdlib only, no `rich` dependency)
- Falls back to plain text if `NO_COLOR` env var is set

### Acceptance criteria

```python
configure(exporter="console")
with tracer.span("chat", model="gpt-4o"):
    pass
# → formatted output printed to stdout
# → no file written
```

---

## Phase 6 — OpenAI Integration

**Goal:** Patch the OpenAI client to auto-capture model, tokens, and cost from API responses.

### Install

```
pip install tracium[openai]
```

### New file: `tracium/integrations/openai.py`

```python
def patch():
    """Monkey-patch openai.OpenAI to auto-instrument all chat completions."""
    ...

def normalize_response(response) -> tuple[TokenUsage, ModelInfo, CostBreakdown]:
    """Extract structured data from an openai ChatCompletion response."""
    ...
```

### Auto-patching

```python
from tracium.integrations import openai
# openai.patch() called automatically on import

client = Client()
with tracer.span("chat"):          # span auto-populated from response
    resp = client.chat.completions.create(...)
```

### Field mapping

| OpenAI response field | Tracium field |
|---|---|
| `model` | `ModelInfo.name` |
| `usage.prompt_tokens` | `TokenUsage.input_tokens` |
| `usage.completion_tokens` | `TokenUsage.output_tokens` |
| `usage.total_tokens` | `TokenUsage.total_tokens` |
| `usage.completion_tokens_details.reasoning_tokens` | `TokenUsage.reasoning_tokens` |
| `usage.prompt_tokens_details.cached_tokens` | `TokenUsage.cached_tokens` |

### Pricing table

Ship a static `_pricing.py` with per-model input/output costs ($/1k tokens). Updates via patch releases.

### Acceptance criteria

```python
from tracium.integrations import openai as openai_integration
configure(exporter="jsonl")
# After response: span payload contains populated TokenUsage + CostBreakdown
```

---

## Phase 7 — Additional Provider Integrations

**Goal:** Add Anthropic, Ollama, Groq, and Together AI normalizers.

### New files

```
tracium/integrations/
    anthropic.py    # Claude response normalization
    ollama.py       # Ollama local model normalization
    groq.py         # Groq API normalization
    together.py     # Together AI normalization
```

### Common contract

Each integration module MUST expose:

```python
def patch() -> None: ...
def normalize_response(response) -> tuple[TokenUsage, ModelInfo, CostBreakdown]: ...
```

### Provider-specific notes

| Provider | Notes |
|---|---|
| Anthropic | `input_tokens` / `output_tokens` already match our schema |
| Ollama | No cost data — use `CostBreakdown.zero()` |
| Groq | Sub-millisecond latency; include `duration_ms` |
| Together AI | Model name normalization needed (includes org prefix) |

### Acceptance criteria

- Each provider normalizer produces valid `TokenUsage` + `ModelInfo` + `CostBreakdown`
- `CostBreakdown.zero()` used for providers with no pricing data

---

## Phase 8 — Additional Exporters

**Goal:** Implement OTLP, Webhook, Datadog, and Grafana Loki exporters.

### Files

```
tracium/exporters/
    otlp.py          # OTLP gRPC/HTTP (requires tracium[otlp])
    webhook.py       # HTTP POST with retry logic
    datadog.py       # Datadog log intake API (requires tracium[datadog])
    grafana_loki.py  # Loki push API (requires tracium[grafana-loki])
```

### Batching

All exporters in this phase MUST support batch export:

```python
class BatchExporter:
    buffer_size: int = 100
    flush_interval_secs: float = 5.0
    def flush() -> None: ...
```

### Webhook exporter

- Configurable `endpoint`, `headers`, `timeout`
- Retry on 5xx with exponential backoff (max 3 retries)
- Payload: `{"events": [...]}`  (list of canonical JSON event objects)

### OTLP exporter

- Maps SpanForge events to OTel `LogRecord` with `gen_ai.*` attributes
- Supports both gRPC and HTTP/protobuf transports
- Depends on `opentelemetry-exporter-otlp`

### Acceptance criteria

- Each exporter passes a send/receive integration test
- Webhook exporter retries on 503 and succeeds on second attempt
- OTLP exporter produces schema-valid log records

---

## Phase 9 — Framework Integrations

**Goal:** Provide drop-in integrations for FastAPI, LangChain, LangGraph, and CrewAI.

### Files

```
tracium/integrations/
    fastapi.py       # ASGI middleware + route span injection
    langchain.py     # LangChain callback handler
    langgraph.py     # LangGraph node/edge instrumentation
    crewai.py        # CrewAI task/agent instrumentation
    otel.py          # OTel bridge: forwards OTel spans to Tracium
```

### FastAPI

```python
from tracium.integrations.fastapi import TraciumMiddleware

app.add_middleware(TraciumMiddleware)
# → Each request gets a trace_id; LLM calls inside handlers are automatically nested
```

### LangChain

```python
from tracium.integrations.langchain import TraciumCallbackHandler

chain = MyChain(callbacks=[TraciumCallbackHandler()])
# → LLM calls, tool calls, chain start/end all emit SpanForge events
```

### LangGraph

- Instruments `StateGraph.compile()` to wrap each node as an `agent_step`
- Wraps graph invocation as `agent_run`

### CrewAI

- Instruments `Crew.kickoff()` as `agent_run`
- Each `Task` execution as `agent_step`

### Acceptance criteria

- FastAPI: HTTP endpoint with an LLM call produces a trace with span hierarchy
- LangChain: `LLMChain.run()` emits at least one `SpanPayload` event
- All integrations produce valid SpanForge events

---

## Phase 10 — CLI Tooling

**Goal:** `tracium` command available after `pip install tracium`.

### `pyproject.toml` entry point

```toml
[project.scripts]
tracium = "tracium._cli:main"
```

### Commands

```
tracium validate <file.jsonl>
    Read each line, parse as Event, run schema validation.
    Exit 0 if all valid. Exit 1 + error details if any invalid.

tracium check-compat <file.jsonl>
    Check schema_version compatibility across all events.
    Report events that would be rejected by current consumer version.

tracium audit-chain <file.jsonl>
    Verify HMAC audit chain integrity.
    Requires TRACIUM_SIGNING_KEY env var.

tracium inspect <event_id> <file.jsonl>
    Pretty-print a single event by event_id.

tracium stats <file.jsonl>
    Print summary: event count, event type breakdown, time range, total tokens, total cost.
```

### Acceptance criteria

```bash
tracium validate tracium_events.jsonl   # exits 0
tracium stats tracium_events.jsonl      # prints summary table
```

---

## Phase 11 — Security + Privacy

**Goal:** Wire HMAC signing and PII redaction into the event emission pipeline as opt-in features.

### Signing (spec §18)

```python
configure(
    exporter="jsonl",
    signing_key="base64-encoded-key"
)
# → All emitted events are HMAC-SHA256 signed before export
```

- `sign_event()` called in `EventStream.emit()` when `signing_key` is configured
- Signing happens before `Exporter.export()`

### Redaction (spec §19)

```python
configure(
    exporter="jsonl",
    redaction_policy=RedactionPolicy(sensitivity=Sensitivity.HIGH)
)
```

- `RedactionPolicy.apply()` called on payload before `Event` construction
- Redaction MUST occur before signing and before export
- No raw PII/PHI ever written to the event store

### Acceptance criteria

- Emitted events with signing key have `hmac_signature` field
- `tracium audit-chain` verifies the chain
- Payload fields marked `Redactable` are masked in the output event

---

## Phase 12 — Hardening + Docs + `1.0.0`

**Goal:** Production-ready release.

### Test coverage

- Unit tests for every public API method
- Integration tests for all 6 exporters
- Integration tests for all 5 provider normalizers
- Integration tests for all 5 framework integrations
- Coverage target: ≥90% line coverage on `tracium/` core
- Performance test: emit 10,000 spans, verify <5ms overhead per span

### Documentation

- Full API reference (Sphinx, hosted on `tracium.dev`)
  - `configure()` with all parameters
  - `tracer.span()` / `agent_run()` / `agent_step()`
  - All exporters with configuration examples
  - All provider integrations with setup guides
- Quickstart guide (≤10 minutes to first event)
- Migration guide from `llm_toolkit_schema` → `tracium`
- Security guide (signing + redaction)

### Example applications

1. **`examples/openai_chat.py`** — minimal OpenAI chat with JSONL export
2. **`examples/agent_workflow.py`** — multi-step agent with console export
3. **`examples/fastapi_app.py`** — FastAPI service with request tracing
4. **`examples/langchain_chain.py`** — LangChain Q&A chain with full instrumentation

### Release checklist

- [ ] All tests passing on Python 3.11, 3.12, 3.13
- [ ] `tracium.__version__ == "1.0.0"`
- [ ] `pyproject.toml` classifiers updated to `Development Status :: 5 - Production/Stable`
- [ ] `RELEASE.md` updated
- [ ] GitHub release tagged `v1.0.0`
- [ ] PyPI package published

---

## Dependency Matrix

| Phase | New runtime deps | New dev deps |
|---|---|---|
| 0–4 | *none* (stdlib only) | `pytest`, `pytest-cov` |
| 5 | *none* | — |
| 6 | `openai` (optional extra) | `pytest-mock` |
| 7 | `anthropic`, `ollama`, `groq` (optional extras) | — |
| 8 | `opentelemetry-exporter-otlp`, `requests` (optional extras) | `responses` (mocking) |
| 9 | `fastapi`, `langchain`, `langgraph`, `crewai` (optional extras) | `httpx` |
| 10 | *none* | — |
| 11 | *none* | — |
| 12 | *none* | `sphinx`, `furo`, `pytest-benchmark` |

---

## File Structure (end state after Phase 12)

```
tracium/
    __init__.py            # Public API surface
    config.py              # TraciumConfig + configure()
    _tracer.py             # Tracer singleton
    _span.py               # Span + SpanContextManager
    _stream.py             # Internal EventStream wrapper
    _cli.py                # CLI entry point
    event.py               # Event envelope (from llm_toolkit_schema)
    types.py               # EventType registry
    ulid.py                # ULID generation
    validate.py            # Schema validation
    exceptions.py          # Exception hierarchy
    signing.py             # HMAC signing
    redact.py              # PII redaction
    actor.py               # ActorContext
    consumer.py            # ConsumerRegistry
    governance.py          # GovernancePolicy
    migrate.py             # v1→v2 migration
    deprecations.py        # Deprecation registry
    namespaces/
        __init__.py
        trace.py           # SpanPayload, AgentRunPayload, AgentStepPayload
        cost.py
        cache.py
        eval_.py
        guard.py
        fence.py
        prompt.py
        redact.py
        diff.py
        template.py
        audit.py
    exporters/
        __init__.py
        jsonl.py
        console.py
        otlp.py
        webhook.py
        datadog.py
        grafana_loki.py
    integrations/
        __init__.py
        openai.py
        anthropic.py
        ollama.py
        groq.py
        together.py
        otel.py
        fastapi.py
        langchain.py
        langgraph.py
        crewai.py
    export/                # Re-export compat layer
    compliance/
    stream.py

llm_toolkit_schema/        # Backward-compat shim (deprecation warning only)
    __init__.py

examples/
    openai_chat.py
    agent_workflow.py
    fastapi_app.py
    langchain_chain.py

tests/
    unit/
    integration/
    performance/
```

---

*End of Tracium SDK Implementation Plan*
