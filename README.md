<p align="center">
  <img src="https://raw.githubusercontent.com/llm-toolkit/llm-toolkit-schema/main/docs/_static/logo.png" alt="llm-toolkit-schema" width="120" />
</p>

<h1 align="center">llm-toolkit-schema</h1>

<p align="center">
  <strong>The shared language every LLM tool speaks.</strong><br/>
  A lightweight Python library that gives your AI applications a common, structured way to record, sign, redact, and export events — with zero mandatory dependencies.
</p>

<p align="center">
  <a href="https://pypi.org/project/llm-toolkit-schema/"><img src="https://img.shields.io/pypi/v/llm-toolkit-schema?color=4c8cbf&label=PyPI&logo=pypi&logoColor=white" alt="PyPI version"/></a>
  <a href="https://pypi.org/project/llm-toolkit-schema/"><img src="https://img.shields.io/pypi/pyversions/llm-toolkit-schema?color=4c8cbf&logo=python&logoColor=white" alt="Python versions"/></a>
  <a href="https://pypi.org/project/llm-toolkit-schema/"><img src="https://img.shields.io/pypi/dm/llm-toolkit-schema?color=4c8cbf&label=downloads" alt="Monthly downloads"/></a>
  <img src="https://img.shields.io/badge/coverage-100%25-brightgreen" alt="100% test coverage"/>
  <img src="https://img.shields.io/badge/tests-1302%20passing-brightgreen" alt="1302 tests"/>
  <img src="https://img.shields.io/badge/dependencies-zero-brightgreen" alt="Zero dependencies"/>
  <a href="docs/index.md"><img src="https://img.shields.io/badge/docs-local-4c8cbf" alt="Documentation"/></a>
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT license"/>
</p>

---

## What is this?

> Think of `llm-toolkit-schema` as a **universal receipt format** for your AI application.
> Every time your app calls a language model, makes a decision, redacts private data, or checks a guardrail — this library gives that action a consistent, structured record that any tool in your stack can read.

Without a shared schema, every team invents their own log format. With `llm-toolkit-schema`, your logs, dashboards, compliance reports, and monitoring tools all speak the same language — automatically.

---

## Why use it?

| Without llm-toolkit-schema | With llm-toolkit-schema |
|---|---|
| Each service logs events differently | Every event follows the same structure |
| Hard to audit who saw what data | Built-in HMAC signing creates a tamper-proof audit trail |
| PII scattered across logs | First-class PII redaction before data leaves your app |
| Vendor-specific observability | OpenTelemetry-compatible — works with any monitoring stack |
| No way to check compatibility | CLI + programmatic compliance checks in CI |
| Complex integration glue | Zero required dependencies — just `pip install` |

---

## Install

```bash
pip install llm-toolkit-schema
```

```python
import llm_toolkit_schema  # that's it — no configuration needed
```

**Requires Python 3.9 or later.** No other packages are required for core usage.

### Optional extras

```bash
pip install "llm-toolkit-schema[jsonschema]"   # strict JSON Schema validation
pip install "llm-toolkit-schema[http]"         # Webhook + OTLP export
pip install "llm-toolkit-schema[pydantic]"     # Pydantic v2 model layer
pip install "llm-toolkit-schema[otel]"         # OpenTelemetry SDK integration
pip install "llm-toolkit-schema[kafka]"        # EventStream.from_kafka() via kafka-python
pip install "llm-toolkit-schema[langchain]"    # LangChain callback handler
pip install "llm-toolkit-schema[llamaindex]"   # LlamaIndex event handler
pip install "llm-toolkit-schema[datadog]"      # Datadog APM + metrics exporter
pip install "llm-toolkit-schema[all]"          # everything above
```

---

## Five-minute tour

### 1 — Record an event

```python
from llm_toolkit_schema import Event, EventType, Tags

event = Event(
    event_type=EventType.TRACE_SPAN_COMPLETED,
    source="my-app@1.0.0",          # who emitted this
    org_id="org_acme",              # your organisation
    payload={
        "model": "gpt-4o",
        "prompt_tokens": 512,
        "completion_tokens": 128,
        "latency_ms": 340.5,
    },
    tags=Tags(env="production"),
)

event.validate()         # raises if structure is invalid
print(event.to_json())   # compact JSON string, ready to store or ship
```

Every event gets a **ULID** (a time-sortable unique ID) automatically — no need to generate one yourself.

---

### 2 — Redact private information before logging

```python
from llm_toolkit_schema.redact import Redactable, RedactionPolicy, Sensitivity

policy = RedactionPolicy(min_sensitivity=Sensitivity.PII, redacted_by="policy:gdpr-v1")

# Wrap any string that might contain PII
prompt = Redactable("Call me at 555-867-5309", sensitivity=Sensitivity.PII)

result = policy.apply({"prompt": prompt})
# result["prompt"] → "[REDACTED by policy:gdpr-v1]"
```

`Redactable` is a string wrapper. You mark fields as sensitive at the point where they're created; the policy decides what to remove before the event is written to any log.

---

### 3 — Sign events for tamper-proof audit trails

```python
from llm_toolkit_schema.signing import sign_event, verify_chain, AuditStream

# Sign a single event
signed = sign_event(event, org_secret="my-org-secret")

# Or build a chain — every event references the one before it,
# so any gap or modification is immediately detectable.
stream = AuditStream(org_secret="my-org-secret")
for e in events:
    stream.append(e)

is_valid, violations = verify_chain(stream.events, org_secret="my-org-secret")
```

This is the same principle used in certificate chains and blockchain — each event's signature covers the previous event's signature, so you cannot alter history without breaking the chain.

---

### 4 — Export to anywhere

```python
from llm_toolkit_schema.stream import EventStream
from llm_toolkit_schema.export.jsonl import JSONLExporter
from llm_toolkit_schema.export.webhook import WebhookExporter
from llm_toolkit_schema.export.otlp import OTLPExporter
from llm_toolkit_schema.export.datadog import DatadogExporter
from llm_toolkit_schema.export.grafana import GrafanaLokiExporter

stream = EventStream(events)

# Write everything to a local file
await stream.drain(JSONLExporter("events.jsonl"))

# Ship to your OpenTelemetry collector
await stream.drain(OTLPExporter("http://otel-collector:4318/v1/traces"))

# Send to Datadog APM (traces + metrics)
await stream.drain(DatadogExporter(
    service="my-app",
    env="production",
    agent_url="http://dd-agent:8126",
    api_key="your-dd-api-key",
))

# Push to Grafana Loki
await stream.drain(GrafanaLokiExporter(
    url="http://loki:3100",
    labels={"app": "my-app", "env": "production"},
))

# Fan-out: guard-blocked events → Slack webhook
await stream.route(
    WebhookExporter("https://hooks.slack.com/your-webhook"),
    predicate=lambda e: e.event_type == "llm.guard.blocked",
)
```

#### Kafka source

```python
from llm_toolkit_schema.stream import EventStream

# Drain a Kafka topic directly into an EventStream
stream = EventStream.from_kafka(
    topic="llm-events",
    bootstrap_servers="kafka:9092",
    group_id="analytics",
    max_messages=5000,
)
await stream.drain(exporter)
```

---

### 5 — Check compliance from the command line

```bash
llm-toolkit-schema check-compat events.json
```

```
✓  CHK-1  All required fields present          (500 / 500 events)
✓  CHK-2  Event types valid                    (500 / 500 events)
✓  CHK-3  Source identifiers well-formed       (500 / 500 events)
✓  CHK-5  Event IDs are valid ULIDs            (500 / 500 events)
All checks passed.
```

Drop this into your CI pipeline and catch schema drift before it reaches production.

---

## What's inside the box

<table>
<thead>
<tr><th>Module</th><th>What it does</th><th>For whom</th></tr>
</thead>
<tbody>
<tr>
  <td><code>llm_toolkit_schema.event</code></td>
  <td>The core <code>Event</code> envelope — the one structure all tools share</td>
  <td>Everyone</td>
</tr>
<tr>
  <td><code>llm_toolkit_schema.types</code></td>
  <td>All built-in event type strings (trace, cost, cache, eval, guard…)</td>
  <td>Everyone</td>
</tr>
<tr>
  <td><code>llm_toolkit_schema.redact</code></td>
  <td>PII detection, sensitivity levels, redaction policies</td>
  <td>Data privacy / GDPR teams</td>
</tr>
<tr>
  <td><code>llm_toolkit_schema.signing</code></td>
  <td>HMAC-SHA256 event signing and tamper-evident audit chains</td>
  <td>Security / compliance teams</td>
</tr>
<tr>
  <td><code>llm_toolkit_schema.compliance</code></td>
  <td>Programmatic v1.0 compatibility checks — no pytest required</td>
  <td>Platform / DevOps teams</td>
</tr>
<tr>
  <td><code>llm_toolkit_schema.export</code></td>
  <td>Ship events to files (JSONL), HTTP webhooks, OTLP collectors, Datadog APM, or Grafana Loki</td>
  <td>Infra / observability teams</td>
</tr>
<tr>
  <td><code>llm_toolkit_schema.stream</code></td>
  <td>Fan-out router — one <code>drain()</code> call reaches multiple backends; Kafka source via <code>from_kafka()</code></td>
  <td>Platform engineers</td>
</tr>
<tr>
  <td><code>llm_toolkit_schema.validate</code></td>
  <td>JSON Schema validation against the published v1.0 schema</td>
  <td>All teams</td>
</tr>
<tr>
  <td><code>llm_toolkit_schema.consumer</code></td>
  <td>Declare schema-namespace dependencies; fail fast at startup if version requirements aren’t met</td>
  <td>Platform / integration teams</td>
</tr>
<tr>
  <td><code>llm_toolkit_schema.governance</code></td>
  <td>Policy-based event gating — block prohibited types, warn on deprecated usage, enforce custom rules</td>
  <td>Platform / compliance teams</td>
</tr>
<tr>
  <td><code>llm_toolkit_schema.deprecations</code></td>
  <td>Register and surface per-event-type deprecation notices at runtime</td>
  <td>Library maintainers</td>
</tr>
<tr>
  <td><code>llm_toolkit_schema.integrations</code></td>
  <td>Plug-in adapters for LangChain (<code>LLMSchemaCallbackHandler</code>) and LlamaIndex (<code>LLMSchemaEventHandler</code>)</td>
  <td>App developers</td>
</tr>
<tr>
  <td><code>llm_toolkit_schema.namespaces</code></td>
  <td>Typed payload dataclasses for all 10 built-in event namespaces</td>
  <td>Tool authors</td>
</tr>
<tr>
  <td><code>llm_toolkit_schema.models</code></td>
  <td>Optional Pydantic v2 models for teams that prefer validated schemas</td>
  <td>API / backend teams</td>
</tr>
</tbody>
</table>

---

## Event namespaces

Every event carries a `payload` — a dictionary whose shape is defined by the event's **namespace**. The ten built-in namespaces cover everything from raw model traces to safety guardrails:

| Namespace prefix | Dataclass | What it records |
|---|---|---|
| `llm.trace.*` | `TracePayload` | Model call — tokens, latency, finish reason **(frozen v1)** |
| `llm.cost.*` | `CostPayload` | Per-call cost in USD |
| `llm.cache.*` | `CachePayload` | Cache hit/miss, backend, TTL |
| `llm.eval.*` | `EvalScenarioPayload` | Scores, labels, evaluator identity |
| `llm.guard.*` | `GuardPayload` | Safety classifier output, block decisions |
| `llm.fence.*` | `FencePayload` | Topic constraints, allow/block lists |
| `llm.prompt.*` | `PromptPayload` | Prompt template version, rendered text |
| `llm.redact.*` | `RedactPayload` | PII audit record — what was found and removed |
| `llm.diff.*` | `DiffPayload` | Prompt/response delta between two events |
| `llm.template.*` | `TemplatePayload` | Template registry metadata |

```python
from llm_toolkit_schema.namespaces.trace import TracePayload

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

---

## Quality standards

- **1 302 tests** — unit, integration, property-based (Hypothesis), and performance benchmarks
- **100 % line and branch coverage** — no dead code ships
- **Zero required dependencies** — the entire core runs on Python's standard library alone
- **Typed** — full `py.typed` marker; works with mypy and pyright out of the box
- **Frozen v1 trace schema** — `llm.trace.*` payload fields will never break between minor releases

---

## Project structure

```
llm_toolkit_schema/
├── event.py          ← The Event envelope (start here)
├── types.py          ← EventType enum
├── signing.py        ← HMAC signing & audit chains
├── redact.py         ← PII redaction
├── validate.py       ← JSON Schema validation
├── consumer.py       ← Consumer registry & schema-version compatibility
├── governance.py     ← Event governance policies
├── deprecations.py   ← Per-event-type deprecation tracking
├── compliance/       ← Compatibility checklist suite
├── export/
│   ├── jsonl.py      ← Local file export
│   ├── webhook.py    ← HTTP POST export
│   ├── otlp.py       ← OpenTelemetry export
│   ├── datadog.py    ← Datadog APM traces + metrics
│   └── grafana.py    ← Grafana Loki export
├── stream.py         ← EventStream fan-out router (+ Kafka source)
├── integrations/
│   ├── langchain.py  ← LangChain callback handler
│   └── llamaindex.py ← LlamaIndex event handler
├── namespaces/       ← Typed payload dataclasses
│   ├── trace.py        (frozen v1)
│   ├── cost.py
│   ├── cache.py
│   └── …
├── models.py         ← Optional Pydantic v2 models
└── migrate.py        ← Schema migration helpers & v2 roadmap
```

---

## Development setup

```bash
git clone https://github.com/llm-toolkit/llm-toolkit-schema.git
cd llm-toolkit-schema

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -e ".[dev]"
pytest                          # run all 1 302 tests
```

<details>
<summary><strong>Code quality commands</strong></summary>

```bash
ruff check .                  # linting
ruff format .                 # auto-format
mypy llm_toolkit_schema       # type checking
pytest --cov                  # tests + coverage report
```

</details>

<details>
<summary><strong>Build the docs locally</strong></summary>

```bash
pip install -e ".[docs]"
cd docs
sphinx-build -b html . _build/html   # open _build/html/index.html
```

</details>

---

## Compatibility & versioning

This project follows [Semantic Versioning](https://semver.org/):

- **Patch** releases (`1.0.x`) — bug fixes only, fully backwards-compatible
- **Minor** releases (`1.x.0`) — new features, backwards-compatible
- **Major** releases (`x.0.0`) — breaking changes, announced in advance

The `llm.trace.*` namespace payload schema is **additionally frozen at v1**: even a major release will not remove or rename fields from `TracePayload`.

---

## Changelog

See [docs/changelog.md](docs/changelog.md) or the [release history on PyPI](https://pypi.org/project/llm-toolkit-schema/#history).

---

## Contributing

Contributions are welcome! Please read the [Contributing Guide](docs/contributing.md) first, then open an issue or pull request.

Key rules:
- All new code must maintain **100 % test coverage**
- Follow the existing **Google-style docstrings**
- Run `ruff` and `mypy` before submitting

---

## License

[MIT](LICENSE) — free for personal and commercial use.

---

<p align="center">
  Made with care for the LLM Developer Toolkit ecosystem.<br/>
  <a href="https://pypi.org/project/llm-toolkit-schema/">PyPI</a> ·
  <a href="docs/index.md">Docs</a> ·
  <a href="docs/quickstart.md">Quickstart</a> ·
  <a href="docs/api/index.md">API Reference</a> ·
  <a href="https://github.com/llm-toolkit/llm-toolkit-schema/issues">Report a bug</a>
</p>
