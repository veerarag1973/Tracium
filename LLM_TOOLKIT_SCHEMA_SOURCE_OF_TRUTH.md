# llm-toolkit-schema — Source of Truth

**Version:** 1.1.2  
**Date:** March 3, 2026  
**Status:** Production/Stable  
**Author:** Sriram  

---

## Table of Contents

1. [What Is llm-toolkit-schema?](#1-what-is-llm-toolkit-schema)
2. [The Problem It Solves](#2-the-problem-it-solves)
3. [Design Philosophy](#3-design-philosophy)
4. [Architecture Overview](#4-architecture-overview)
5. [The Event Model](#5-the-event-model)
6. [Event Namespaces and Payload Schemas](#6-event-namespaces-and-payload-schemas)
7. [Security — HMAC Signing and Audit Chains](#7-security--hmac-signing-and-audit-chains)
8. [Privacy — PII Redaction Framework](#8-privacy--pii-redaction-framework)
9. [Observability — The Export Pipeline](#9-observability--the-export-pipeline)
10. [Event Stream and Routing](#10-event-stream-and-routing)
11. [Compliance and Governance](#11-compliance-and-governance)
12. [Schema Validation](#12-schema-validation)
13. [Consumer Registry and Version Compatibility](#13-consumer-registry-and-version-compatibility)
14. [Deprecation and Migration Framework](#14-deprecation-and-migration-framework)
15. [Ecosystem Integrations](#15-ecosystem-integrations)
16. [The CLI](#16-the-cli)
17. [Pydantic Model Layer](#17-pydantic-model-layer)
18. [Engineering Standards and Quality](#18-engineering-standards-and-quality)
19. [Module Reference](#19-module-reference)
20. [Installation and Extras](#20-installation-and-extras)
21. [Version History and Roadmap](#21-version-history-and-roadmap)
22. [Positioning in the Ecosystem](#22-positioning-in-the-ecosystem)

---

## 1. What Is llm-toolkit-schema?

`llm-toolkit-schema` is a **foundational Python library** that defines the shared event contract for the entire LLM Developer Toolkit ecosystem. It answers one specific, critical question:

> *When an LLM application records something — a model call, a cost figure, a cache hit, a safety block, a PII redaction — what does that record look like, exactly?*

The answer is an `Event`: a strictly typed, cryptographically signable, PII-aware, OpenTelemetry-compatible envelope that every tool in the toolkit emits and every observability backend can consume.

**In one sentence:** `llm-toolkit-schema` is the universal receipt format for AI applications.

```
pip install llm-toolkit-schema
```

```python
from llm_toolkit_schema import Event, EventType, Tags

event = Event(
    event_type=EventType.TRACE_SPAN_COMPLETED,
    source="my-app@1.0.0",
    org_id="org_acme",
    payload={"model": "gpt-4o", "prompt_tokens": 512, "latency_ms": 340.5},
    tags=Tags(env="production"),
)

event.validate()
print(event.to_json())
```

Every event receives a **ULID** (a time-sortable, globally unique identifier) automatically at creation time. No external service, no coordination, no UUID v4 randomness you cannot sort.

---

## 2. The Problem It Solves

### The Fragmentation Problem

When teams build LLM-powered applications today, every service logs events in its own format. The model-call service emits one JSON structure. The safety-check service emits another. The cost-tracking service emits a third. These formats drift apart over time.

The consequences are real and expensive:

| Domain | Consequence of No Shared Schema |
|---|---|
| **Observability** | Dashboards must be rebuilt per service; no cross-service correlation |
| **Compliance / Audit** | No tamper-evident trail; impossible to prove what happened in what order |
| **Data Privacy** | PII appears in logs because no one owns the redaction contract |
| **Debugging** | Trace IDs and span IDs are not interoperable; cannot correlate events across tools |
| **Tooling** | Every new tool must write custom parsers for every upstream log format |
| **CI/CD** | Schema drift reaches production silently because there is no compatibility gate |

### What This Library Provides

`llm-toolkit-schema` establishes a **single, stable contract** that all tools share:

- One event envelope with fixed, validated fields
- One set of namespaced event type strings (50+ covering 10 domains)
- One signing algorithm (HMAC-SHA256 chain) that makes tamper detection trivial
- One PII redaction API so privacy is enforced at the data source
- One export abstraction so any tool can ship events to any backend (JSONL, webhook, OTLP, Datadog, Grafana Loki)
- One CLI command to check schema compliance in CI before it becomes a production incident

---

## 3. Design Philosophy

The design decisions behind this library are deliberate and non-negotiable. Understanding them explains every API choice.

### Zero Required Dependencies

The core library — event creation, validation, signing, redaction — runs on Python's standard library alone. No `requests`, no `pydantic`, no `opentelemetry-sdk` required for the core paths.

**Why:** A foundational library that imposes dependencies becomes a dependency conflict waiting to happen. Every tool that builds on this schema would inherit those conflicts. By requiring nothing, the library installs cleanly into any environment.

Optional extras exist for teams that want Pydantic models, the OpenTelemetry SDK, Kafka ingestion, or framework integrations — but they are always opt-in.

### Typed Exceptions Everywhere

Every validation failure raises a `SchemaValidationError` with three fields: the field name, the received value, and a human-readable reason. No bare `ValueError("bad input")`. No `assert` statements in library code.

**Why:** Structured exceptions are machine-parseable. Downstream tooling can catch `SchemaValidationError`, read `exc.field` and `exc.received`, and produce actionable error messages without parsing a string.

### Immutability After Construction

Once an `Event` is created and validated, its envelope fields are read-only. The `payload` property returns a `MappingProxyType` — a read-only view of the internal dict. Mutation attempts raise `TypeError` immediately.

**Why:** Events are frequently passed across module boundaries and into export queues. If any consumer could mutate an event after it was created, signed events would become invalid and audit trails would become unreliable.

### Deterministic Serialisation

`Event.to_json()` always produces the same JSON string for the same event — keys are sorted alphabetically at every nesting level, `None` values are omitted, datetimes are formatted as `YYYY-MM-DDTHH:MM:SS.ffffffZ`. This is not a convenience feature — it is a security requirement.

**Why:** The HMAC signature is computed over the canonical JSON of the payload. If serialisation were non-deterministic, signing and verification would produce different results on different machines, making the audit chain useless.

### Namespace-Based Event Types

All event types follow the pattern `llm.<namespace>.<entity>.<action>`:

```
llm.trace.span.completed
llm.guard.output.blocked
llm.cost.token.recorded
llm.redact.pii.detected
```

**Why:** This is directly inspired by OpenTelemetry's semantic conventions. It makes event types machine-parseable, enables prefix-based routing (`e.event_type.startswith("llm.guard.")`), and prevents naming collisions across independent tools.

### ULIDs, Not UUIDs

Every `event_id` is a **ULID** — a 128-bit identifier with 48 bits of millisecond-precision timestamp at the front and 80 bits of randomness at the back. ULIDs are:

- **Time-sortable** — you can sort events chronologically by ID alone, without reading the timestamp field
- **Lexicographically ordered** — they sort correctly as strings in any database
- **Monotonic within the same millisecond** — no risk of disorder in high-throughput streams
- **Zero-coordination** — generated locally, globally unique, no sequence service required

The ULID implementation in `llm_toolkit_schema/ulid.py` is written entirely in the standard library. No `python-ulid` package is required.

---

## 4. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        llm-toolkit-schema                            │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                      Core Layer                              │    │
│  │  event.py · types.py · ulid.py · exceptions.py · models.py  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│           │               │               │               │         │
│  ┌────────▼───┐  ┌────────▼───┐  ┌───────▼────┐  ┌──────▼──────┐  │
│  │  Security  │  │  Privacy   │  │ Namespaces │  │  Validation  │  │
│  │ signing.py │  │  redact.py │  │ namespaces/│  │ validate.py  │  │
│  └────────────┘  └────────────┘  └────────────┘  └─────────────┘  │
│           │               │               │               │         │
│  ┌────────▼───────────────▼───────────────▼───────────────▼──────┐ │
│  │               Platform Layer                                   │ │
│  │  stream.py · governance.py · consumer.py · compliance/         │ │
│  │  deprecations.py · migrate.py                                  │ │
│  └───────────────────────────────────────────────────────────────┘ │
│           │                                                          │
│  ┌────────▼───────────────────────────────────────────────────────┐ │
│  │               Export Layer                                      │ │
│  │  export/jsonl.py · export/webhook.py · export/otlp.py          │ │
│  │  export/datadog.py · export/grafana.py                         │ │
│  └───────────────────────────────────────────────────────────────┘ │
│           │                                                          │
│  ┌────────▼───────────────────────────────────────────────────────┐ │
│  │               Integrations Layer                                │ │
│  │  integrations/langchain.py · integrations/llamaindex.py        │ │
│  └───────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

The architecture is a deliberate **vertical stack**. Each layer builds only on the layer below it. The core layer has no knowledge of exporters. Exporters have no knowledge of signers. This makes each layer independently testable and replaceable.

---

## 5. The Event Model

The `Event` class — defined in `llm_toolkit_schema/event.py` — is the single most important type in the library. Everything else serves it.

### Envelope Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `schema_version` | `str` | Yes | Always `"1.0"` — identifies the envelope spec version |
| `event_id` | `str` | Auto | ULID — generated automatically if not provided |
| `event_type` | `EventType \| str` | Yes | Namespaced string — must match `llm.<ns>.<entity>.<action>` |
| `timestamp` | `datetime \| str` | Auto | UTC ISO-8601 — set to `datetime.now(UTC)` if not provided |
| `source` | `str` | Yes | `tool-name@semver` — e.g. `"my-app@1.0.0"` |
| `payload` | `dict` | Yes | Namespace-specific data; returned as `MappingProxyType` |
| `trace_id` | `str` | No | 32 lowercase hex chars — W3C TraceContext compatible |
| `span_id` | `str` | No | 16 lowercase hex chars — W3C TraceContext compatible |
| `parent_span_id` | `str` | No | Parent span for distributed trace stitching |
| `org_id` | `str` | No | Organisation identifier — used for multi-tenant isolation checks |
| `team_id` | `str` | No | Team within an org |
| `actor_id` | `str` | No | User or service account that produced the event |
| `session_id` | `str` | No | Conversation or request session grouping |
| `tags` | `Tags` | No | Arbitrary string key→value metadata |
| `checksum` | `str` | No | `sha256:<hex>` — payload integrity check, set by `sign()` |
| `signature` | `str` | No | `hmac-sha256:<hex>` — chain signature, set by `sign()` |
| `prev_id` | `str` | No | ULID of the preceding event — set by `AuditStream` |

### Tags

`Tags` is an immutable key-value container accepting only non-empty strings for both keys and values. It serialises to a JSON object with sorted keys.

```python
tags = Tags(env="production", model="gpt-4o", region="us-east-1")
tags["env"]          # "production"
"model" in tags      # True
tags.to_dict()       # {"env": "production", "model": "gpt-4o", "region": "us-east-1"}
```

### Serialisation

```python
# To JSON string (canonical, sorted keys, no None values)
json_str = event.to_json()

# To plain dict (for further processing)
data = event.to_dict()

# Round-trip: deserialise from JSON or dict
event2 = Event.from_json(json_str)
event3 = Event.from_dict(data)

# Validation (raises SchemaValidationError if anything is wrong)
event.validate()
```

The serialisation contract guarantees that the same `Event` always produces byte-for-byte identical JSON. This is the foundation that makes HMAC signing reliable across processes, machines, and Python versions.

---

## 6. Event Namespaces and Payload Schemas

The library defines **10 built-in namespaces**, each with a dedicated typed payload dataclass in `llm_toolkit_schema/namespaces/`. These dataclasses have a `to_dict()` method for feeding directly into `Event(payload=...)`.

| Namespace | Dataclass | What It Records | Stability |
|---|---|---|---|
| `llm.trace.*` | `TracePayload` | Model call — tokens, latency, finish reason | **Frozen v1** |
| `llm.cost.*` | `CostPayload` | Per-call cost in USD; model pricing tier | Stable |
| `llm.cache.*` | `CachePayload` | Cache hit/miss, backend type, TTL, key hash | Stable |
| `llm.eval.*` | `EvalScenarioPayload` | Evaluation scores, labels, evaluator identity | Stable |
| `llm.guard.*` | `GuardPayload` | Safety classifier output, block decisions | Stable |
| `llm.fence.*` | `FencePayload` | Topic constraints, allow/block lists | Stable |
| `llm.prompt.*` | `PromptPayload` | Prompt template version, rendered text hash | Stable |
| `llm.redact.*` | `RedactPayload` | PII audit record — categories found and removed | Stable |
| `llm.diff.*` | `DiffPayload` | Prompt/response delta between two events | Stable |
| `llm.template.*` | `TemplatePayload` | Template registry metadata, variable bindings | Stable |

### The Frozen v1 Trace Schema

The `llm.trace.*` namespace is **contractually frozen at v1**. Fields will never be removed or renamed in any minor or patch release. This is the namespace used by every LLM call instrumentation tool, and breaking it would cascade across the entire ecosystem.

```python
from llm_toolkit_schema.namespaces.trace import TracePayload
from llm_toolkit_schema import Event

payload = TracePayload(
    model="gpt-4o",
    prompt_tokens=512,
    completion_tokens=128,
    latency_ms=340.5,
    finish_reason="stop",
)

event = Event(
    event_type="llm.trace.span.completed",
    source="my-app@1.0.0",
    payload=payload.to_dict(),
)
```

### Runtime Policy Classes

Three namespaces (v1.1.1) gained companion policy classes that enforce runtime behavior:

- **`GuardPolicy`** — input/output guardrail enforcement with configurable fail-open/fail-closed mode and injectable checker functions
- **`FencePolicy`** — structured-output validation driver with retry-sequence loop and `max_retries` limit
- **`TemplatePolicy`** — variable presence checking and output validation for prompt-template workflows

---

## 7. Security — HMAC Signing and Audit Chains

The `llm_toolkit_schema/signing.py` module provides **compliance-grade audit log integrity** without requiring a blockchain, a distributed ledger, or any external service. The implementation uses only Python's standard `hashlib` and `hmac` modules.

### The Signing Algorithm

Signing an event is a two-step computation:

```
step 1:  checksum  = "sha256:"      + SHA-256( canonical_payload_json ).hexdigest()
step 2:  sig_input = event_id + "|" + checksum + "|" + (prev_id or "")
         signature = "hmac-sha256:" + HMAC-SHA256( sig_input, org_secret ).hexdigest()
```

The canonical payload JSON uses `sort_keys=True` and compact separators — the same deterministic serialisation described in §5. This ensures the checksum is identical regardless of Python version or dict insertion order.

### Single-Event Signing

```python
from llm_toolkit_schema.signing import sign_event, verify_event

signed = sign_event(event, org_secret="my-org-secret")

# signed.checksum  → "sha256:a3f8..."
# signed.signature → "hmac-sha256:7c2d..."

is_valid = verify_event(signed, org_secret="my-org-secret")  # True
```

### The Audit Chain

The real value is chain signatures. Every event in an `AuditStream` contains the `event_id` of its predecessor in the `prev_id` field. The signature of each event is computed over `event_id + checksum + prev_id`. This creates a **hash chain** — the same mechanism used in X.509 certificate chains and git commit graphs.

```
event[0]: prev_id=None,          signature=HMAC(id[0] + chk[0] + "")
event[1]: prev_id=event[0].id,   signature=HMAC(id[1] + chk[1] + id[0])
event[2]: prev_id=event[1].id,   signature=HMAC(id[2] + chk[2] + id[1])
```

If any event is modified, inserted, or deleted, every signature after that point will fail to verify. There is no way to tamper with the history and maintain a valid chain.

```python
from llm_toolkit_schema.signing import AuditStream, verify_chain

stream = AuditStream(org_secret="my-org-secret", source="audit-daemon@1.0.0")
for e in raw_events:
    stream.append(e)

result = verify_chain(stream.events, org_secret="my-org-secret")
# result.valid          → True/False
# result.first_tampered → event_id of the first modified event (if any)
# result.gaps           → list of missing prev_id links (deletions are visible)
# result.tampered_count → total number of invalid signatures
```

### Key Rotation

The HMAC key can be rotated without breaking the chain. `AuditStream.rotate_key()` inserts a signed `AUDIT_KEY_ROTATED` event into the chain, then switches the active signing key. `verify_chain()` accepts a `key_map` argument mapping rotation event IDs to their corresponding new secrets.

### Security Guarantees

- The `org_secret` **never** appears in any exception message, `__repr__`, or `__str__` output
- All signature comparisons use `hmac.compare_digest()` — immune to timing-based side-channel attacks
- Empty or whitespace-only secrets are rejected immediately at signing time
- Signing failures always raise `SigningError` — they never silently pass

---

## 8. Privacy — PII Redaction Framework

The `llm_toolkit_schema/redact.py` module provides a **first-class PII redaction API** that operates at the field level, before event data is written to any log or exported to any backend.

### Core Design Decision: Mark at Source, Decide at Policy

PII redaction is opt-in **per field** at the point of creation. The policy decides what to remove. This separation ensures that the sensitivity of a field is recorded in the code where the field is constructed — not deferred to a post-processing step where context is lost.

### Sensitivity Levels

```
LOW  →  MEDIUM  →  HIGH  →  PII  →  PHI
```

- `LOW` — internal-only data you'd prefer not to expose, but not personally identifying
- `MEDIUM` — business-sensitive data (e.g., customer tier, pricing)
- `HIGH` — data that could identify an individual indirectly
- `PII` — Personally Identifiable Information (names, email addresses, phone numbers)
- `PHI` — Protected Health Information (HIPAA-regulated)

### Usage

```python
from llm_toolkit_schema.redact import Redactable, RedactionPolicy, Sensitivity

# Mark fields as sensitive at the point of construction
prompt_text = Redactable(
    "Call me at 555-867-5309, my name is Alice",
    sensitivity=Sensitivity.PII
)

# Configure a policy — redact anything PII or above
policy = RedactionPolicy(
    min_sensitivity=Sensitivity.PII,
    redacted_by="policy:gdpr-v1"
)

# Apply the policy — returns new dict with sensitive values replaced
result = policy.apply({"prompt": prompt_text, "model": "gpt-4o"})
# result["prompt"]  → "[REDACTED by policy:gdpr-v1]"
# result["model"]   → "gpt-4o"  (not sensitive, passed through)
```

### Post-Redaction Assertion

```python
from llm_toolkit_schema.redact import contains_pii, assert_redacted

# Check programmatically
if contains_pii(result):
    raise RuntimeError("PII leak detected after redaction policy")

# Or assert (raises RedactionError on failure)
assert_redacted(result, min_sensitivity=Sensitivity.PII)
```

### Security Guarantee

`Redactable` content **never** appears in exception messages or stack traces. If a `Redactable` value triggers a validation error, the exception reports the field name and sensitivity level — never the value itself.

---

## 9. Observability — The Export Pipeline

The `llm_toolkit_schema/export/` package provides **async exporters** that ship events to observability backends. All exporters implement the `Exporter` protocol — an object with an `async export_batch(events)` method. Any object satisfying this structural protocol can be used without inheriting from a base class.

### Built-in Exporters

#### JSONL Exporter

Writes events to a local file in Newline-Delimited JSON format. Optionally compresses each event with gzip.

```python
from llm_toolkit_schema.export.jsonl import JSONLExporter

exporter = JSONLExporter("audit-log.jsonl")
await exporter.export_batch(events)
```

#### Webhook Exporter

POSTs events to any HTTP endpoint. Supports custom headers, retry backoff, and timeout configuration. The target URL is validated as `http://` or `https://` at construction time — not at first use.

```python
from llm_toolkit_schema.export.webhook import WebhookExporter

exporter = WebhookExporter(
    "https://hooks.slack.com/your-webhook",
    headers={"Authorization": "Bearer token"},
    retries=3,
)
await exporter.export_batch(events)
```

#### OTLP Exporter

Ships events to any OpenTelemetry collector using the OTLP/HTTP JSON protocol. Supports gzip compression, configurable `batch_size` (events are chunked — the parameter is actually applied, not silently ignored), and resource attribute injection.

```python
from llm_toolkit_schema.export.otlp import OTLPExporter

exporter = OTLPExporter(
    "http://otel-collector:4318/v1/traces",
    batch_size=100,
    gzip=True,
)
await exporter.export_batch(events)
```

#### Datadog Exporter

Sends events as Datadog APM trace spans (via the local Agent) **and** as Datadog metrics series (via the public API). No `ddtrace` dependency — all transport is stdlib HTTP. Span and trace IDs are **deterministic SHA-256 derivations** of the event ID, so Datadog's deduplication logic works correctly across retries.

```python
from llm_toolkit_schema.export.datadog import DatadogExporter, DatadogResourceAttributes

exporter = DatadogExporter(
    service="my-llm-app",
    env="production",
    agent_url="http://dd-agent:8126",
    api_key="your-dd-api-key",
    resource=DatadogResourceAttributes(service="my-llm-app", env="production"),
)
await exporter.export_batch(events)
```

#### Grafana Loki Exporter

Pushes events to Grafana Loki via the `/loki/api/v1/push` HTTP endpoint. Supports multi-tenant deployments via the `X-Scope-OrgID` header.

```python
from llm_toolkit_schema.export.grafana import GrafanaLokiExporter

exporter = GrafanaLokiExporter(
    url="http://loki:3100",
    labels={"app": "my-llm-app", "env": "production"},
    tenant_id="org-acme",
)
await exporter.export_batch(events)
```

#### OTel Bridge Exporter

Ships events through any configured OpenTelemetry `TracerProvider` — useful when a `TracerProvider` is already set up in your application (e.g. via `opentelemetry-sdk` auto-instrumentation). Requires the optional `otel` extra.

```bash
pip install "llm-toolkit-schema[otel]"
```

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor

# Configure the global TracerProvider (done once at startup)
provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)

# Export events through the active TracerProvider
from llm_toolkit_schema.export.otel_bridge import OTelBridgeExporter

exporter = OTelBridgeExporter(
    tracer_name="llm-toolkit-schema",
    tracer_version="1.0",
)
exporter.export(event)               # single event
await exporter.export_batch(events)  # or a batch
```

Unlike `OTLPExporter` (which speaks the wire protocol directly), `OTelBridgeExporter` uses the OTel SDK's own span lifecycle — context propagation, sampling, and all registered `SpanProcessor` instances fire normally.

---

### OpenTelemetry Compliance

As of v1.1.2, `llm-toolkit-schema` is **100% compliant** with the OpenTelemetry specification. The table below summarises every required attribute and how it is fulfilled:

| OTel Requirement | How It Is Fulfilled |
|------------------|---------------------|
| `gen_ai.system` | Emitted from `payload.model_info.provider` |
| `gen_ai.request.model` | Emitted from `payload.model_info.name` |
| `gen_ai.usage.input_tokens` | Emitted from `payload.token_usage.prompt` |
| `gen_ai.usage.output_tokens` | Emitted from `payload.token_usage.completion` |
| `gen_ai.operation.name` | Emitted from `payload.span_name` |
| `gen_ai.response.finish_reasons` | Emitted from `payload.status` |
| `deployment.environment.name` | `ResourceAttributes.deployment_environment` (semconv 1.21+ key) |
| `spanKind: CLIENT (3)` | Set on every `to_otlp_span()` output |
| `traceFlags: 1` (sampled) | Set on every span and traceparent header |
| `endTimeUnixNano` | Computed as `startTimeUnixNano + duration_ms × 1 000 000` |
| `status.code` / `status.message` | Mapped from `payload.status` (`"error"/"timeout"` → ERROR, `"ok"` → OK) |
| W3C TraceContext propagation | `make_traceparent()` / `extract_trace_context()` |
| OTel SDK integration | `OTelBridgeExporter` (optional `[otel]` extra) |

### W3C TraceContext Utilities

Two helper functions in `llm_toolkit_schema.export.otlp` implement [W3C TraceContext (RFC 9429)](https://www.w3.org/TR/trace-context/) header propagation:

```python
from llm_toolkit_schema.export.otlp import make_traceparent, extract_trace_context

# Build a traceparent header from an event's IDs
header = make_traceparent(event.trace_id, event.span_id)
# → "00-<32-hex-trace-id>-<16-hex-span-id>-01"

# Parse incoming headers to resume a trace
ctx = extract_trace_context({"traceparent": header})
# ctx = {"trace_id": "...", "span_id": "...", "sampled": True}
```

Pass `sampled=False` to produce an unsampled `traceparent` (`-00` suffix). The `tracestate` vendor extension header is parsed and returned when present.

---

## 10. Event Stream and Routing

`llm_toolkit_schema/stream.py` provides `EventStream` — an **immutable, ordered sequence** of events with a fluent API for filtering, routing, and fan-out export.

### Core API

```python
from llm_toolkit_schema.stream import EventStream

stream = EventStream([event1, event2, event3])

# Filter by predicate
guard_events = stream.filter(lambda e: e.event_type.startswith("llm.guard."))

# Filter by exact event type
traces = stream.filter_by_type("llm.trace.span.completed")

# Drain all events to an exporter
await stream.drain(JSONLExporter("traces.jsonl"))

# Route specific events to a target (fan-out)
await stream.route(
    WebhookExporter("https://hooks.slack.com/..."),
    predicate=lambda e: e.event_type == "llm.guard.output.blocked",
)
```

### Loading from Different Sources

```python
# From a JSONL file (buffered)
stream = EventStream.from_file("audit.jsonl")

# Streaming iterator (memory-efficient, does not buffer entire file)
for event in iter_file("audit.jsonl"):
    process(event)

# Async streaming iterator
async for event in aiter_file("audit.jsonl"):
    await process(event)

# From an asyncio Queue
stream = await EventStream.from_async_queue(queue, max_messages=1000)

# From a Kafka topic (requires [kafka] extra)
stream = EventStream.from_kafka(
    topic="llm-events",
    bootstrap_servers="kafka:9092",
    group_id="analytics",
    max_messages=5000,
)
await stream.drain(exporter)
```

### The Exporter Protocol

Any object with `async def export_batch(self, events: Sequence[Event]) -> Any` satisfies the `Exporter` protocol. No inheritance required — this is structural subtyping. This means you can write a custom exporter in five lines and pass it directly to `stream.drain()`.

---

## 11. Compliance and Governance

### Event Governance Policies

`llm_toolkit_schema/governance.py` provides a **three-tier policy engine** for controlling which event types are allowed in your system.

```python
from llm_toolkit_schema.governance import EventGovernancePolicy, set_global_policy

policy = EventGovernancePolicy(
    # Hard block: raises GovernanceViolationError
    blocked_types={"llm.legacy.trace.v0"},

    # Soft block: emits GovernanceWarning but does not raise
    warn_deprecated={"llm.eval.score.recorded.v1"},

    # Enforce custom rules: arbitrary callable predicates
    custom_rules=[
        lambda e: None if e.org_id else "org_id is required in production"
    ],

    # Block event types not registered in EventType enum
    strict_unknown=True,
)

# Apply globally — all check_event() calls use this policy
set_global_policy(policy)
```

### Programmatic Compliance Checks

`llm_toolkit_schema/compliance/` provides five built-in checks that can be run programmatically — no pytest, no test framework needed. These are designed for use in CI pipelines and startup health checks:

| Check ID | What It Verifies |
|---|---|
| `CHK-1` | All required fields are present on every event |
| `CHK-2` | All `event_type` values are valid registered strings |
| `CHK-3` | All `source` identifiers follow the `tool@semver` format |
| `CHK-5` | All `event_id` values are valid ULIDs |

```python
from llm_toolkit_schema.compliance import test_compatibility

result = test_compatibility(events)
# result.passed  → True/False
# result.checks  → {"CHK-1": True, "CHK-2": True, ...}
# result.details → per-check failure messages
```

Additional compliance functions:

- `verify_tenant_isolation(events)` — detects cross-tenant data leakage in multi-org deployments
- `verify_events_scoped(events, org_id)` — confirms all events belong to the expected org
- `verify_chain_integrity(events, org_secret)` — wraps `verify_chain()` with gap, tamper, and timestamp-monotonicity diagnostics

---

## 12. Schema Validation

`llm_toolkit_schema/validate.py` validates an event against the **published v1.0 JSON Schema** at `schemas/v1.0/schema.json`.

Two validation paths are available:

1. **jsonschema backend** (when `jsonschema>=4.21` is installed) — full JSON Schema Draft 7 validation with precise error paths
2. **stdlib fallback** — structural field-type checks without an additional dependency

```python
from llm_toolkit_schema.validate import validate_event

validate_event(event)  # raises SchemaValidationError if invalid
```

The regex patterns used in validation match the prefixed formats produced by the signing module:
- `checksum` must match `^sha256:[0-9a-f]{64}$`
- `signature` must match `^hmac-sha256:[0-9a-f]{64}$`

---

## 13. Consumer Registry and Version Compatibility

`llm_toolkit_schema/consumer.py` solves a specific distribution problem: when you have 10 tools built on this schema, how does each tool declare exactly which schema namespaces it depends on, and how does a platform operator verify that all installed tools are compatible with the installed schema version?

```python
from llm_toolkit_schema.consumer import ConsumerRegistry

registry = ConsumerRegistry()
registry.register(
    consumer_id="llm-trace@0.3.1",
    requires_namespace="llm.trace",
    min_version="1.0.0",
    max_version="1.x",
)

# Fails immediately at startup if schema version is incompatible
registry.assert_compatible()
```

This is designed to be called at application startup — **fail fast** before any events are processed, not at runtime when the first incompatible event arrives.

---

## 14. Deprecation and Migration Framework

### Deprecation Registry

`llm_toolkit_schema/deprecations.py` provides a structured registry for announcing that specific event types are deprecated, with precise sunset timelines and replacement guidance.

```python
from llm_toolkit_schema.deprecations import DeprecationRegistry, warn_if_deprecated

registry = DeprecationRegistry()
warn_if_deprecated("llm.legacy.eval.scored", registry)
# Emits DeprecationWarning with migration guidance if registered
```

### Migration Roadmap

`llm_toolkit_schema/migrate.py` contains the **v2.0 migration roadmap** — a structured list of all event types scheduled to change in the next major version, each with:

- `since` — the version in which the deprecation was announced
- `sunset` — the version in which the type will be removed
- `sunset_policy` — urgency classification (`NEXT_MAJOR`, `NEXT_MINOR`, `LONG_TERM`, `UNSCHEDULED`)
- `replacement` — the new event type to migrate to
- `field_renames` — a dict mapping old field names to new field names

```python
from llm_toolkit_schema.migrate import v2_migration_roadmap

roadmap = v2_migration_roadmap()
# Returns 9 DeprecationRecord entries, sorted by event_type
```

---

## 15. Ecosystem Integrations

### LangChain

`LLMSchemaCallbackHandler` is a LangChain `BaseCallbackHandler` that automatically emits structured `llm.trace.*` events for every LLM call and tool invocation. Plug it in once; every model call in the chain is instrumented.

```python
from llm_toolkit_schema.integrations.langchain import LLMSchemaCallbackHandler

handler = LLMSchemaCallbackHandler(
    source="my-langchain-app@1.0.0",
    org_id="org_acme",
    exporter=OTLPExporter("http://otel-collector:4318/v1/traces"),
)

chain = my_chain.with_config(callbacks=[handler])
```

Requires: `pip install "llm-toolkit-schema[langchain]"`

### LlamaIndex

`LLMSchemaEventHandler` is a LlamaIndex callback event handler covering query, retrieval, and response events.

```python
from llm_toolkit_schema.integrations.llamaindex import LLMSchemaEventHandler
from llama_index.core import Settings

Settings.callback_manager.add_handler(
    LLMSchemaEventHandler(source="my-llama-app@1.0.0")
)
```

Requires: `pip install "llm-toolkit-schema[llamaindex]"`

---

## 16. The CLI

The `llm-toolkit-schema` command-line interface is installed as a script entry point. All sub-commands are designed for use in CI pipelines.

### check-compat

Reads a JSON file of serialised events and prints compliance violations:

```
llm-toolkit-schema check-compat events.json

✓  CHK-1  All required fields present          (500 / 500 events)
✓  CHK-2  Event types valid                    (500 / 500 events)
✓  CHK-3  Source identifiers well-formed       (500 / 500 events)
✓  CHK-5  Event IDs are valid ULIDs            (500 / 500 events)
All checks passed.
```

### list-deprecated

Prints all deprecation notices from the global registry:

```
llm-toolkit-schema list-deprecated
```

### migration-roadmap

Prints the v2.0 migration roadmap in human-readable or machine-readable JSON:

```
llm-toolkit-schema migration-roadmap
llm-toolkit-schema migration-roadmap --json
```

### check-consumers

Lists all registered consumers and their version compatibility status:

```
llm-toolkit-schema check-consumers
```

---

## 17. Pydantic Model Layer

`llm_toolkit_schema/models.py` provides an optional **Pydantic v2 model layer** for teams that prefer validator-first schema definitions over the core dataclass approach.

```python
from llm_toolkit_schema.models import EventModel

# Build a Pydantic model from an existing Event
model = EventModel.from_event(event)
model.model_json_schema()   # Full JSON Schema for the event envelope

# Convert back to a core Event
restored = model.to_event()
```

This layer is deliberately optional — it requires `pip install "llm-toolkit-schema[pydantic]"`. Teams that do not use Pydantic pay zero cost for this capability existing.

---

## 18. Engineering Standards and Quality

### Test Coverage

- **1,302 tests** across unit, integration, property-based (Hypothesis), and performance benchmark suites
- **100% line and branch coverage** — the CI gate is set to `--cov-fail-under=100`; any untested line blocks the build
- Tests run in parallel via `pytest-xdist` for fast CI feedback

### Test Categories

| Marker | Description |
|---|---|
| `@pytest.mark.unit` | Fast, isolated tests — no I/O, no network |
| `@pytest.mark.integration` | Tests that cross module boundaries |
| `@pytest.mark.perf` | Performance benchmarks with regression detection via `pytest-benchmark` |
| `@pytest.mark.security` | Security-focused tests: timing attacks, secret leakage, tamper detection |

### Property-Based Testing

Critical invariants are verified with **Hypothesis** — a library that generates thousands of inputs automatically to find edge cases. The ULID generator, the signing algorithm, and the serialisation contract all have property-based test suites.

Example invariant: `Event.from_json(event.to_json()) == event` must hold for any valid event, regardless of payload content.

### Type Safety

- Full `py.typed` marker — the package is typed for consumers that use mypy or pyright
- mypy is run in `--strict` mode: `disallow_untyped_defs`, `disallow_any_generics`, `warn_return_any`, `no_implicit_reexport`
- All public APIs have complete type annotations

### Performance Targets

Verified by the benchmark suite (`@pytest.mark.perf`):

| Operation | Target |
|---|---|
| Event creation | < 1ms |
| Event creation + HMAC signing | < 5ms |
| Serialisation (`to_json`) | < 1ms |
| Chain verification (1000 events) | < 500ms |

### Code Quality Tooling

| Tool | Purpose |
|---|---|
| `ruff` | Linting (replaces flake8, isort, pyupgrade, bandit-lite) with 30+ rule categories enabled |
| `mypy --strict` | Static type checking |
| `pre-commit` | Enforces lint and format checks before every commit |

Ruff rules enabled include: `pycodestyle`, `pyflakes`, `isort`, `pep8-naming`, `pyupgrade`, `flake8-bugbear`, `flake8-bandit` (security), `pydocstyle` (Google convention), `pylint` subset, `perflint`, and Ruff-native rules.

### Documentation Style

All public docstrings follow **Google-style** conventions. Sphinx with the `pydata-sphinx-theme` generates the hosted documentation at `https://llm-toolkit-schema.readthedocs.io`.

---

## 19. Module Reference

| Module | Public Symbols | Purpose |
|---|---|---|
| `llm_toolkit_schema.event` | `Event`, `Tags`, `SCHEMA_VERSION` | Core event envelope |
| `llm_toolkit_schema.types` | `EventType` | All 50+ registered event type strings |
| `llm_toolkit_schema.ulid` | `generate()`, `validate()`, `extract_timestamp_ms()` | ULID utilities |
| `llm_toolkit_schema.exceptions` | `LLMSchemaError`, `SchemaValidationError`, `SigningError`, `VerificationError`, `ULIDError`, `SerializationError`, `DeserializationError`, `EventTypeError` | Exception hierarchy |
| `llm_toolkit_schema.redact` | `Redactable`, `RedactionPolicy`, `Sensitivity`, `RedactionResult`, `contains_pii()`, `assert_redacted()` | PII redaction |
| `llm_toolkit_schema.signing` | `sign_event()`, `verify_event()`, `verify_chain()`, `AuditStream`, `assert_verified()` | HMAC signing and audit chains |
| `llm_toolkit_schema.validate` | `validate_event()` | JSON Schema validation |
| `llm_toolkit_schema.stream` | `EventStream`, `Exporter`, `iter_file()`, `aiter_file()` | Event routing and fan-out |
| `llm_toolkit_schema.export.jsonl` | `JSONLExporter` | Local JSONL file export |
| `llm_toolkit_schema.export.webhook` | `WebhookExporter` | HTTP webhook export |
| `llm_toolkit_schema.export.otlp` | `OTLPExporter` | OpenTelemetry OTLP/HTTP export |
| `llm_toolkit_schema.export.datadog` | `DatadogExporter`, `DatadogResourceAttributes` | Datadog APM + metrics |
| `llm_toolkit_schema.export.grafana` | `GrafanaLokiExporter` | Grafana Loki push |
| `llm_toolkit_schema.governance` | `EventGovernancePolicy`, `GovernanceViolationError`, `GovernanceWarning`, `set_global_policy()`, `check_event()` | Policy engine |
| `llm_toolkit_schema.compliance` | `test_compatibility()`, `verify_tenant_isolation()`, `verify_chain_integrity()` | CI compliance checks |
| `llm_toolkit_schema.consumer` | `ConsumerRegistry`, `ConsumerRecord`, `IncompatibleSchemaError` | Version dependency declaration |
| `llm_toolkit_schema.deprecations` | `DeprecationRegistry`, `DeprecationNotice`, `warn_if_deprecated()`, `list_deprecated()` | Deprecation tracking |
| `llm_toolkit_schema.migrate` | `v2_migration_roadmap()`, `SunsetPolicy`, `DeprecationRecord`, `MigrationResult` | v2 migration roadmap |
| `llm_toolkit_schema.governance` | `EventGovernancePolicy` | Policy-based event gating |
| `llm_toolkit_schema.models` | `EventModel` | Optional Pydantic v2 models |
| `llm_toolkit_schema.namespaces.*` | `TracePayload`, `CostPayload`, `CachePayload`, `EvalScenarioPayload`, `GuardPayload`, `FencePayload`, `PromptPayload`, `RedactPayload`, `DiffPayload`, `TemplatePayload` | Typed payload dataclasses |
| `llm_toolkit_schema.integrations.langchain` | `LLMSchemaCallbackHandler` | LangChain integration |
| `llm_toolkit_schema.integrations.llamaindex` | `LLMSchemaEventHandler` | LlamaIndex integration |

---

## 20. Installation and Extras

### Core Installation

```bash
pip install llm-toolkit-schema
```

Requires **Python 3.9 or later**. No other packages are required for core event creation, signing, redaction, and validation.

### Optional Extras

| Extra | Adds | Use When |
|---|---|---|
| `[jsonschema]` | `jsonschema>=4.21` | Full JSON Schema Draft 7 validation |
| `[http]` | `httpx>=0.27` | Webhook and OTLP HTTP export |
| `[pydantic]` | `pydantic>=2.7` | Pydantic v2 model layer |
| `[otel]` | `opentelemetry-sdk>=1.24` | Direct OpenTelemetry SDK integration |
| `[kafka]` | `kafka-python>=2.0` | `EventStream.from_kafka()` |
| `[langchain]` | `langchain-core>=0.2` | `LLMSchemaCallbackHandler` |
| `[llamaindex]` | `llama-index-core>=0.10` | `LLMSchemaEventHandler` |
| `[datadog]` | *(stdlib only)* | `DatadogExporter` |
| `[all]` | Everything above | Development / full integration environments |

```bash
pip install "llm-toolkit-schema[langchain,kafka,datadog]"
pip install "llm-toolkit-schema[all]"
```

### Development Setup

```bash
git clone https://github.com/llm-toolkit/llm-toolkit-schema.git
cd llm-toolkit-schema

python -m venv .venv
.venv\Scripts\activate             # Windows
source .venv/bin/activate          # macOS / Linux

pip install -e ".[dev]"
pytest                             # runs all 1302 tests with coverage
```

---

## 21. Version History and Roadmap

### Version Timeline

| Version | Date | Milestone |
|---|---|---|
| `0.1.0` | 2026-01-25 | Core `Event`, `EventType`, `Tags`, ULID, JSON serialisation, exception hierarchy |
| `0.2.0` | 2026-02-01 | PII redaction framework, Pydantic v2 model layer |
| `0.3.0` | 2026-02-08 | HMAC signing, audit chains, key rotation |
| `0.4.0` | 2026-02-15 | OTLP, Webhook, JSONL exporters, `EventStream` router |
| `0.5.0` | 2026-02-22 | All 10 namespace payload dataclasses, published JSON Schema, `validate_event()` |
| `1.0.0` | 2026-03-01 | GA release — compliance package, `check-compat` CLI, performance benchmarks |
| `1.0.1` | 2026-03-01 | Package renamed: `llm_schema` → `llm_toolkit_schema` (stable import path) |
| `1.1.0` | 2026-03-01 | Datadog + Grafana Loki exporters, Kafka source, governance, consumer registry, LangChain + LlamaIndex integrations, deprecation registry, migration roadmap |
| `1.1.1` | 2026-03-15 | Security and correctness fixes: immutable payload, `strict_unknown` fix, regex alignment, deterministic Datadog IDs, `iter_file()` / `aiter_file()` |
| `1.1.2` | 2026-03-15 | Full OpenTelemetry compliance: `gen_ai.*` semconv, `deployment.environment.name`, `spanKind`, `traceFlags`, `endTimeUnixNano`, error status mapping, W3C TraceContext utilities, `OTelBridgeExporter` |

### Versioning Policy

This project follows [Semantic Versioning](https://semver.org/):

- **Patch** (`1.0.x`) — bug fixes only, fully backwards-compatible
- **Minor** (`1.x.0`) — new features, backwards-compatible, existing APIs unchanged
- **Major** (`x.0.0`) — breaking changes, announced in advance with migration documentation

The `llm.trace.*` namespace is **additionally frozen at v1**: fields will not be removed or renamed even across major releases.

### v2.0 Roadmap

The `v2_migration_roadmap()` function enumerates 9 event types scheduled for changes in v2.0. The migration framework — `DeprecationRecord`, `SunsetPolicy`, `field_renames` — was built specifically to make this transition manageable for downstream consumers.

---

## 22. Positioning in the Ecosystem

### The One Rule

> Do not start building `promptlock`, `llm-trace`, or any other tool in the LLM Developer Toolkit until `llm-toolkit-schema` is complete, stable, and all namespace payload schemas are reviewed and frozen.

This was the governing principle throughout development. `llm-toolkit-schema` is build order **#1** — not because it is the simplest piece, but because every other tool's correctness depends on the contract it defines.

### What Makes This Different from Rolling Your Own

Most teams that instrument LLM applications write their own log schemas. The common failure modes are:

1. **No signing** — no way to prove an audit trail has not been tampered with
2. **No redaction contract** — PII appears wherever the code author forgot to filter
3. **No type validation** — events arrive with missing fields months after the code was written
4. **No export abstraction** — switching from "write to file" to "send to Datadog" requires rewriting instrumentation
5. **No versioning** — breaking schema changes arrive silently in a dependency update

`llm-toolkit-schema` addresses all five from the first `pip install`. The zero-dependency core means there is no cost to adopting it early, before you know which backends you will need.

### OpenTelemetry Compatibility

Events are designed to map cleanly to the OTLP trace format. The `trace_id` and `span_id` fields follow W3C TraceContext conventions (32 and 16 lowercase hex characters, respectively). The OTLP exporter translates `Event` objects to valid OTLP spans with full semantic-convention compliance:

- **`gen_ai.*` attributes** (GenAI semconv 1.27+) — model name, provider, token usage, finish reason, and operation name are all emitted as first-class `gen_ai.*` OTLP attributes, enabling native dashboards in Grafana, Honeycomb, and Dynatrace.
- **`deployment.environment.name`** — resource attribute uses the correct semconv 1.21+ key name (supersedes the legacy `deployment.environment`).
- **`spanKind: CLIENT`** — every emitted span carries `kind: 3` as required by the OTLP specification.
- **W3C TraceContext (RFC 9429)** — `make_traceparent()` and `extract_trace_context()` in `llm_toolkit_schema.export.otlp` implement full `traceparent`/`tracestate` header propagation.
- **OTel SDK bridge** — `OTelBridgeExporter` (optional `[otel]` extra) integrates with any configured `TracerProvider`, enabling interop with auto-instrumentation pipelines.

This means events produced by this library appear natively in Jaeger, Tempo, Grafana, and any other OTLP-compatible backend — with LLM-specific metrics visible out of the box.

### Relationship to the Broader Toolkit

`llm-toolkit-schema` is the **foundation layer** for a family of tools:

```
llm-toolkit-schema        ← this library (build first)
       │
       ├── llm-trace       ← model call tracing tool
       ├── promptlock       ← prompt versioning and locking
       ├── llm-guard        ← safety guardrail evaluation
       ├── llm-cost         ← token cost tracking
       └── ...              ← any tool that emits structured LLM events
```

Any tool that emits events conforming to this schema is immediately compatible with any tool that consumes them. That is the entire point: **interoperability through a shared contract**.

---

*This document is the authoritative reference for `llm-toolkit-schema` v1.1.2. It supersedes all other summaries, design notes, and implementation plan documents for the purpose of explaining the project to external audiences.*

*For the full API reference, see [llm-toolkit-schema.readthedocs.io](https://llm-toolkit-schema.readthedocs.io).*  
*For the source code, see [github.com/llm-toolkit/llm-toolkit-schema](https://github.com/llm-toolkit/llm-toolkit-schema).*  
*For the published package, see [pypi.org/project/llm-toolkit-schema](https://pypi.org/project/llm-toolkit-schema/).*
