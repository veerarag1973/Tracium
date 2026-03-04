# llm-toolkit-schema v2.0 — Implementation Plan

**Date:** March 3, 2026
**Target version:** 2.0.0
**Status:** Ready for development
**Constraint:** Nothing downstream is mature. All types can be redesigned from scratch. Get it right.

---

## The four design principles

1. **OTel-native** — field names match `gen_ai.*` semconv 1.27+ exactly. No translation layer needed at export time. We don't invent names for things OTel has already named.
2. **Agent-aware** — spans model tool calls, reasoning steps, and decision points as first-class children, not embedded lists. A complete multi-step agent run is representable as a span tree with parent/child relationships.
3. **Cost and tokens first-class** — `TokenUsage` covers every token category all major providers expose today. `CostBreakdown` is a typed value object, never `Optional[float]`.
4. **Vendor-neutral** — `GenAISystem` enum covers all OTel-defined providers. A `ProviderNormalizer` protocol lets any provider's raw response be normalized to the schema in one call.

---

## What changes vs. current state

| Area | Current | v2.0 |
|---|---|---|
| `ModelInfo.provider` | Free string | `GenAISystem` enum |
| `TokenUsage` fields | `prompt_tokens`, `completion_tokens`, `total_tokens` | `input_tokens`, `output_tokens`, `total_tokens`, `cached_tokens`, `reasoning_tokens`, `image_tokens` |
| `SpanCompletedPayload` | No span IDs, no parent linkage, no operation kind | `span_id`, `trace_id`, `parent_span_id`, `agent_run_id`, `operation` (`GenAIOperationName`) |
| Cost | `cost_usd: Optional[float]` on span | Typed `CostBreakdown` value object with per-category breakdown |
| Agent runs | Not representable | `AgentStepPayload` + `AgentRunPayload` with full span tree |
| Reasoning steps | Not modelled | `ReasoningStep` value object (o1/o3/Claude extended thinking) |
| Eval scores | Separate payload with no span link | `EvalScorePayload` links to `span_id` directly |
| Provider normalization | None — raw names used | `ProviderNormalizer` protocol + built-in normalizers |
| `FROZEN v1` marker | Present on `SpanCompletedPayload` | Removed — there are no frozen types in v2.0 |

---

## File structure after v2.0

```
llm_toolkit_schema/
    otel.py                  â† NEW: GenAISystem, GenAIOperationName, SpanKind enums
    normalize.py             â† NEW: ProviderNormalizer protocol + built-in normalizers
    actor.py                 â† EXISTS: ActorContext (keep as-is)
    event.py                 â† Minor update: schema version bump
    types.py                 â† Add new EventType entries for agent + reasoning
    namespaces/
        trace.py             â† REWRITE: SpanPayload, AgentStepPayload, AgentRunPayload
        cost.py              â† REWRITE: CostBreakdown, PricingTier, CostRecordedPayload
        eval_.py             â† UPDATE: EvalScorePayload links to span_id
        prompt.py            â† EXISTS: keep (already complete)
        inspect.py           â† EXISTS: keep (already complete)
        diff.py              â† EXISTS: keep (already complete)
        guard.py             â† EXISTS: keep (already complete)
        cache.py             â† EXISTS: keep (already complete)
        redact.py            â† EXISTS: keep (already complete)
        template.py          â† EXISTS: keep (already complete)
        fence.py             â† EXISTS: keep (already complete)
```

---

## Workstream 1 — OTel primitives (`otel.py`)

**File:** `llm_toolkit_schema/otel.py`
**Depends on:** nothing — implement first, everything else depends on this

### 1.1 `GenAISystem` enum

Canonical list matching OTel semconv `gen_ai.system` attribute.
No free strings anywhere in the schema — every model provider maps to an entry here.

```python
class GenAISystem(str, Enum):
    OPENAI            = "openai"
    ANTHROPIC         = "anthropic"
    COHERE            = "cohere"
    VERTEX_AI         = "vertex_ai"
    AWS_BEDROCK       = "aws_bedrock"
    AZ_AI_INFERENCE   = "az.ai.inference"   # Azure AI Studio / GitHub Models
    GROQ              = "groq"
    OLLAMA            = "ollama"
    MISTRAL_AI        = "mistral_ai"
    TOGETHER_AI       = "together_ai"
    HUGGING_FACE      = "hugging_face"
    CUSTOM            = "_custom"           # private/enterprise deployments
```

Rules:
- `CUSTOM` requires a `custom_system_name: str` companion field wherever it is used
- Serialises to its string value — OTel-compatible without conversion
- `from_string(value: str) -> GenAISystem` classmethod: case-insensitive lookup, falls back to `CUSTOM`

### 1.2 `GenAIOperationName` enum

Canonical operation names matching OTel semconv `gen_ai.operation.name`.

```python
class GenAIOperationName(str, Enum):
    CHAT              = "chat"
    TEXT_COMPLETION   = "text_completion"
    EMBEDDINGS        = "embeddings"
    IMAGE_GENERATION  = "image_generation"
    EXECUTE_TOOL      = "execute_tool"
    INVOKE_AGENT      = "invoke_agent"
    CREATE_AGENT      = "create_agent"
    REASONING         = "reasoning"       # isolated reasoning/thinking steps
```

### 1.3 `SpanKind` enum

Maps to OTel `SpanKind` values relevant to LLM operations.

```python
class SpanKind(str, Enum):
    CLIENT   = "CLIENT"    # outbound LLM API calls — most common
    SERVER   = "SERVER"    # incoming agent requests
    INTERNAL = "INTERNAL"  # internal reasoning / routing steps
    CONSUMER = "CONSUMER"  # tool execution triggered by LLM output
    PRODUCER = "PRODUCER"  # events emitted by an agent for downstream consumption
```

---

## Workstream 2 — Token and cost types (rewrite of `trace.py` and `cost.py`)

**Depends on:** Workstream 1 (`GenAISystem`)

### 2.1 `TokenUsage` — full rewrite

Replace the 3-field v1 with one that covers every token category all major providers expose today.

| Field | Type | Description |
|---|---|---|
| `input_tokens` | `int` | Tokens in the prompt/input (OTel: `gen_ai.usage.input_tokens`) |
| `output_tokens` | `int` | Tokens in the completion/output (OTel: `gen_ai.usage.output_tokens`) |
| `total_tokens` | `int` | Sum as reported by provider |
| `cached_tokens` | `Optional[int]` | Input tokens served from cache (OpenAI prompt caching / Anthropic cache read) |
| `cache_creation_tokens` | `Optional[int]` | Tokens written to cache (Anthropic `cache_creation_input_tokens`) |
| `reasoning_tokens` | `Optional[int]` | Chain-of-thought tokens (OpenAI o1/o3) |
| `image_tokens` | `Optional[int]` | Tokens representing image inputs in multimodal calls |

Migration: `prompt_tokens` â†’ `input_tokens`, `completion_tokens` â†’ `output_tokens`.

### 2.2 `ModelInfo` — rewrite to use `GenAISystem`

| Field | Type | Description |
|---|---|---|
| `system` | `GenAISystem` | Provider (replaces `provider: str`) — OTel: `gen_ai.system` |
| `name` | `str` | Model as requested — OTel: `gen_ai.request.model` |
| `response_model` | `Optional[str]` | Model that actually responded (differs in gateway/fallback) — OTel: `gen_ai.response.model` |
| `version` | `Optional[str]` | Model version string |
| `custom_system_name` | `Optional[str]` | Required when `system == GenAISystem.CUSTOM` |

Validation: `custom_system_name` must be set and non-empty whenever `system == CUSTOM`.

### 2.3 `CostBreakdown` — new value object (replaces `cost_usd: Optional[float]`)

Never a plain float. Always a typed breakdown so consumers and audit systems can see what they're paying for.

| Field | Type | Description |
|---|---|---|
| `input_cost_usd` | `float` | Cost for input/prompt tokens |
| `output_cost_usd` | `float` | Cost for output/completion tokens |
| `cached_discount_usd` | `float` | Savings from cache hits (stored as positive, subtracted from total) |
| `reasoning_cost_usd` | `float` | Cost for reasoning tokens (0.0 if not applicable) |
| `total_cost_usd` | `float` | `input + output + reasoning - cached_discount` |
| `currency` | `str` | ISO 4217, default `"USD"` |
| `pricing_date` | `str` | ISO 8601 date the pricing snapshot was taken (for auditability) |

Validation: `total_cost_usd` must equal `input_cost_usd + output_cost_usd + reasoning_cost_usd - cached_discount_usd` within floating-point tolerance (1e-6).

### 2.4 `PricingTier` — new value object

Captures per-provider, per-model pricing at the time the cost was recorded. Cost records are worthless without this — provider prices change and reproduced calculations 6 months later need to know the rates at call time.

| Field | Type | Description |
|---|---|---|
| `system` | `GenAISystem` | Provider |
| `model` | `str` | Model name |
| `input_per_million_usd` | `float` | USD per 1M input tokens |
| `output_per_million_usd` | `float` | USD per 1M output tokens |
| `cached_input_per_million_usd` | `Optional[float]` | Discounted rate for cached input tokens |
| `reasoning_per_million_usd` | `Optional[float]` | Rate for reasoning tokens (o1/o3) |
| `effective_date` | `str` | ISO 8601 date these rates were valid |

### 2.5 `ToolCall` — extend existing

Add fields missing for proper OTel tracing and provider parity:

| New field | Type | Description |
|---|---|---|
| `span_id` | `Optional[str]` | OTel span ID for this tool call — enables parent-child linking |
| `tool_call_id` | `Optional[str]` | Provider-assigned ID (OpenAI and Anthropic include this in responses) |
| `error_type` | `Optional[str]` | OTel `error.type` attribute when `status == "error"` |
| `error_message` | `Optional[str]` | Human-readable error detail |

### 2.6 `SpanPayload` — full rewrite (replaces `SpanCompletedPayload`)

The central type. Every field is mandatory unless it genuinely cannot exist for all operation types.

| Field | Type | Description |
|---|---|---|
| `span_id` | `str` | 16 lowercase hex chars (OTel 8-byte span ID) |
| `trace_id` | `str` | 32 lowercase hex chars (OTel 16-byte trace ID) |
| `parent_span_id` | `Optional[str]` | 16 hex chars — `None` for root spans |
| `agent_run_id` | `Optional[str]` | Groups all spans from one agent invocation |
| `span_name` | `str` | Human-readable e.g. `"chat gpt-4o"` |
| `operation` | `GenAIOperationName` | What kind of LLM operation this span represents |
| `span_kind` | `SpanKind` | OTel span kind — default `CLIENT` |
| `status` | `str` | `"ok"`, `"error"`, `"timeout"` |
| `start_time_unix_nano` | `int` | OTel-aligned start timestamp |
| `end_time_unix_nano` | `int` | OTel-aligned end timestamp |
| `duration_ms` | `float` | Derived from start/end for convenience |
| `model` | `Optional[ModelInfo]` | Required for `chat`, `text_completion`, `embeddings` |
| `token_usage` | `Optional[TokenUsage]` | Required when a model is involved |
| `cost` | `Optional[CostBreakdown]` | `None` only when pricing information is unavailable |
| `tool_calls` | `List[ToolCall]` | Empty list (not `None`) when no tools were called |
| `error` | `Optional[str]` | Short error message |
| `error_type` | `Optional[str]` | OTel `error.type` attribute |
| `attributes` | `Dict[str, Any]` | Escape hatch for provider-specific attributes not in the schema. Empty dict by default. |

Validation additions:
- `span_id` must be exactly 16 lowercase hex characters
- `trace_id` must be exactly 32 lowercase hex characters
- `parent_span_id`, if set, must be exactly 16 lowercase hex characters
- `end_time_unix_nano >= start_time_unix_nano`
- `duration_ms` must match `(end_time_unix_nano - start_time_unix_nano) / 1_000_000` within 1ms tolerance

### 2.7 `CostRecordedPayload` — full rewrite

| Field | Type | Description |
|---|---|---|
| `span_id` | `str` | Links to `SpanPayload.span_id` (replaces `span_event_id`) |
| `trace_id` | `str` | Links to the trace for rollup queries |
| `agent_run_id` | `Optional[str]` | For agent-level cost aggregation |
| `model` | `ModelInfo` | Which model incurred this cost |
| `token_usage` | `TokenUsage` | Token breakdown |
| `cost` | `CostBreakdown` | Typed cost breakdown — never optional here |
| `pricing` | `Optional[PricingTier]` | Pricing snapshot used to compute cost |
| `recorded_at_unix_nano` | `int` | When the cost record was created |

---

## Workstream 3 — Agent span hierarchy (additions to `trace.py`)

**Depends on:** Workstream 2
**New EventTypes:** `TRACE_AGENT_STEP`, `TRACE_AGENT_COMPLETED`, `TRACE_REASONING_STEP`

### 3.1 `ReasoningStep` — new value object

For models that expose chain-of-thought (OpenAI o1/o3, Claude 3.5/3.7 extended thinking, Gemini thinking mode).

| Field | Type | Description |
|---|---|---|
| `step_index` | `int` | Zero-based index within the span |
| `reasoning_tokens` | `int` | Tokens consumed by this reasoning step |
| `duration_ms` | `Optional[float]` | Wall-clock time for this step |
| `content_hash` | `Optional[str]` | SHA-256 of the reasoning content — the content itself is never stored |

> **Design decision:** Raw reasoning content is intentionally not stored — only its hash. This is a deliberate privacy and IP-protection decision. The hash is sufficient for tamper detection and audit trail purposes. Document this in the RFC with the full rationale.

### 3.2 `DecisionPoint` — new value object

Captures a branching decision made by an agent — what it considered, what it chose, and why.

| Field | Type | Description |
|---|---|---|
| `decision_id` | `str` | Unique within the agent run |
| `decision_type` | `str` | `"tool_selection"`, `"route_choice"`, `"loop_termination"`, `"escalation"` |
| `options_considered` | `List[str]` | What the agent had available to choose from |
| `chosen_option` | `str` | What it chose |
| `rationale` | `Optional[str]` | Why — available for models that expose reasoning, absent for black-box models |

### 3.3 `AgentStepPayload` — new payload for `llm.trace.agent.step`

One step in a multi-step agent loop. Links into the same span tree as `SpanPayload`.

| Field | Type | Description |
|---|---|---|
| `agent_run_id` | `str` | Groups all steps from this agent invocation |
| `step_index` | `int` | Zero-based position in the agent loop |
| `span_id` | `str` | This step's OTel span ID |
| `trace_id` | `str` | The trace this step belongs to |
| `parent_span_id` | `Optional[str]` | Parent span — typically the `agent_run` root span |
| `operation` | `GenAIOperationName` | What happened in this step |
| `model` | `Optional[ModelInfo]` | Model used — absent for tool-only steps |
| `token_usage` | `Optional[TokenUsage]` | Token consumption for this step |
| `cost` | `Optional[CostBreakdown]` | Cost for this step |
| `tool_calls` | `List[ToolCall]` | Tools invoked in this step |
| `reasoning_steps` | `List[ReasoningStep]` | Chain-of-thought steps (o1/o3/extended thinking) |
| `decision_points` | `List[DecisionPoint]` | Branching decisions made in this step |
| `status` | `str` | `"ok"`, `"error"`, `"timeout"` |
| `start_time_unix_nano` | `int` | Step start |
| `end_time_unix_nano` | `int` | Step end |
| `duration_ms` | `float` | Derived from start/end |

### 3.4 `AgentRunPayload` — new payload for `llm.trace.agent.completed`

Root-level summary event for a complete multi-step agent execution. The single event that gives you the full picture of a run.

| Field | Type | Description |
|---|---|---|
| `agent_run_id` | `str` | Unique ID for this run — stable across all steps |
| `agent_name` | `str` | Name of the agent e.g. `"customer-support-bot"` |
| `trace_id` | `str` | The OTel trace this run belongs to |
| `root_span_id` | `str` | The root span that contains all child spans |
| `total_steps` | `int` | How many steps were executed |
| `total_model_calls` | `int` | How many LLM API calls were made across all steps |
| `total_tool_calls` | `int` | How many tool invocations occurred across all steps |
| `total_token_usage` | `TokenUsage` | Aggregated across all steps |
| `total_cost` | `CostBreakdown` | Aggregated across all steps |
| `status` | `str` | Final outcome: `"ok"`, `"error"`, `"timeout"`, `"max_steps_exceeded"` |
| `start_time_unix_nano` | `int` | Run start |
| `end_time_unix_nano` | `int` | Run end |
| `duration_ms` | `float` | Total wall-clock time |
| `termination_reason` | `Optional[str]` | Why the run ended — human-readable |

---

## Workstream 4 — Vendor normalisation layer (`normalize.py`)

**Depends on:** Workstream 1 + Workstream 2
**File:** `llm_toolkit_schema/normalize.py`

### 4.1 `ProviderNormalizer` protocol

```python
class ProviderNormalizer(Protocol):
    system: GenAISystem

    def normalize_model(self, response: dict) -> ModelInfo: ...
    def normalize_tokens(self, response: dict) -> TokenUsage: ...
    def normalize_cost(
        self,
        token_usage: TokenUsage,
        model: str,
        pricing: Optional[PricingTier] = None,
    ) -> Optional[CostBreakdown]: ...
```

### 4.2 Built-in normalizers

**`OpenAINormalizer`** — processes raw OpenAI API response dicts:
- `usage.prompt_tokens` â†’ `input_tokens`
- `usage.completion_tokens` â†’ `output_tokens`
- `usage.prompt_tokens_details.cached_tokens` â†’ `cached_tokens`
- `usage.completion_tokens_details.reasoning_tokens` â†’ `reasoning_tokens`
- `model` â†’ `ModelInfo.name` and `ModelInfo.response_model`
- `system_fingerprint` â†’ stored in `attributes`

**`AnthropicNormalizer`** — processes raw Anthropic API response dicts:
- `usage.input_tokens` â†’ `input_tokens` (already matches)
- `usage.output_tokens` â†’ `output_tokens` (already matches)
- `usage.cache_read_input_tokens` â†’ `cached_tokens`
- `usage.cache_creation_input_tokens` â†’ `cache_creation_tokens`
- `model` â†’ `ModelInfo.name`

**`OllamaNormalizer`** — processes raw Ollama API response dicts:
- `prompt_eval_count` â†’ `input_tokens`
- `eval_count` â†’ `output_tokens`
- `total_duration` (nanoseconds) â†’ `duration_ms` on the span

**`GenericNormalizer`** — best-effort fallback for unlisted providers:
- Tries common field names in priority order: `prompt_tokens` / `input_tokens`, `completion_tokens` / `output_tokens`
- Sets `cached_tokens`, `reasoning_tokens` to `None` (provider doesn't expose them)
- Sets `system` to `GenAISystem.CUSTOM`

### 4.3 `normalize_response()` top-level helper

```python
def normalize_response(
    response: dict,
    system: GenAISystem,
    *,
    pricing: Optional[PricingTier] = None,
    custom_normalizer: Optional[ProviderNormalizer] = None,
) -> tuple[ModelInfo, TokenUsage, Optional[CostBreakdown]]:
```

Single call. Takes any raw provider API response dict and returns everything needed to build a `SpanPayload`. No mapping boilerplate in consumer code.

---

## Workstream 5 — Eval integration with span linkage (`eval_.py`)

**Depends on:** Workstream 2
**Goal:** Eval scores attach to spans by `span_id` so dashboards and pipelines can correlate quality scores with specific model calls.

### 5.1 `EvalScorePayload` — replaces `EvalScenarioPayload`

| Field | Type | Description |
|---|---|---|
| `eval_id` | `str` | Unique ID for this eval result |
| `span_id` | `str` | The span this eval result is attached to |
| `trace_id` | `str` | The trace this eval belongs to |
| `agent_run_id` | `Optional[str]` | For agent-level eval aggregation |
| `scenario_id` | `str` | Eval scenario definition identifier |
| `scenario_name` | `str` | Human-readable name |
| `evaluator` | `str` | `"human"`, `"llm-as-judge"`, `"heuristic"`, `"embedding-similarity"` |
| `status` | `str` | `"passed"`, `"failed"`, `"skipped"` |
| `score` | `Optional[float]` | Primary score in `[0.0, 1.0]` |
| `metrics` | `Dict[str, float]` | All metrics (empty dict, not `None`) |
| `baseline_score` | `Optional[float]` | Comparison baseline |
| `duration_ms` | `Optional[float]` | Time to run the eval |
| `recorded_at_unix_nano` | `int` | When the eval was recorded |

### 5.2 `EvalRegressionPayload` — update

Add `span_id`, `trace_id`, `agent_run_id` fields to match the rest of the schema.

---

## New `EventType` entries for v2.0

Add to `types.py` under `llm.trace.*`:

```
TRACE_AGENT_STEP        = "llm.trace.agent.step"
TRACE_AGENT_COMPLETED   = "llm.trace.agent.completed"
TRACE_REASONING_STEP    = "llm.trace.reasoning.step"
```

Add under `llm.cost.*`:

```
COST_ATTRIBUTED         = "llm.cost.attributed"   # agent-level cost rollup
```

---

## Types to deprecate (not delete — use `llm_toolkit_schema.deprecations`)

| Old type | Replacement | Reason |
|---|---|---|
| `SpanCompletedPayload` | `SpanPayload` | No span IDs, no OTel field names |
| `TokenUsage` (v1 field names) | `TokenUsage` (rewritten) | `prompt_tokens`/`completion_tokens` don't match OTel semconv |
| `ModelInfo.provider: str` | `ModelInfo.system: GenAISystem` | Untyped, not validated |
| `CostRecordedPayload` (old) | `CostRecordedPayload` (rewritten) | `span_event_id`, no `CostBreakdown` |
| `EvalScenarioPayload` | `EvalScorePayload` | No span or trace link |

Old types remain importable and carry a `DeprecationWarning` via the `deprecations` registry. They are removed in v2.1.0.

---

## Test plan

| File | Covers |
|---|---|
| `tests/test_otel.py` | `GenAISystem`, `GenAIOperationName`, `SpanKind` enums, `from_string()` methods, all serialization round-trips |
| `tests/test_trace_v2.py` | `SpanPayload`, `ToolCall` extensions, `ReasoningStep`, `DecisionPoint`, `AgentStepPayload`, `AgentRunPayload` — full construction, validation, round-trip |
| `tests/test_cost_v2.py` | `CostBreakdown` (total validation), `PricingTier`, `CostRecordedPayload` rewrite |
| `tests/test_normalize.py` | All four normalizers, `normalize_response()` helper with real-shape response fixtures for each provider |
| `tests/test_eval_v2.py` | `EvalScorePayload`, `EvalRegressionPayload` updates |

Coverage target: 99%+ maintained.

---

## Day-by-day schedule

### Day 1 — Workstream 1 + Workstream 2 core types

| Time | Task |
|---|---|
| Morning | Create `otel.py`: `GenAISystem`, `GenAIOperationName`, `SpanKind`, `from_string()` |
| Morning | Write `tests/test_otel.py` |
| Afternoon | Rewrite `TokenUsage` (`input_tokens`, `output_tokens` + new fields) |
| Afternoon | Rewrite `ModelInfo` (`system: GenAISystem`, `response_model`, `custom_system_name`) |
| Afternoon | Add `CostBreakdown` and `PricingTier` to `cost.py` |
| Afternoon | Extend `ToolCall` with `span_id`, `tool_call_id`, `error_type` |

### Day 2 — `SpanPayload` rewrite + agent types

| Time | Task |
|---|---|
| Morning | Rewrite `SpanPayload` (full field set, hex ID validation, timestamp consistency) |
| Morning | Rewrite `CostRecordedPayload` using `CostBreakdown` + `span_id` linkage |
| Morning | Write `tests/test_cost_v2.py` |
| Afternoon | Add `ReasoningStep` and `DecisionPoint` value objects |
| Afternoon | Add `AgentStepPayload` and `AgentRunPayload` |
| Afternoon | Add `TRACE_AGENT_*` entries to `types.py` |
| Afternoon | Write `tests/test_trace_v2.py` |

### Day 3 — Normalizers + eval

| Time | Task |
|---|---|
| Morning | Create `normalize.py`: `ProviderNormalizer` protocol |
| Morning | Implement `OpenAINormalizer` and `AnthropicNormalizer` with real response shape fixtures |
| Afternoon | Implement `OllamaNormalizer` and `GenericNormalizer` |
| Afternoon | Implement `normalize_response()` helper |
| Afternoon | Write `tests/test_normalize.py` |
| Afternoon | Rewrite `EvalScorePayload` and update `EvalRegressionPayload` |
| Afternoon | Write `tests/test_eval_v2.py` |

### Day 4 — Integration, deprecations, version bump

| Time | Task |
|---|---|
| Morning | Mark old types deprecated via `llm_toolkit_schema.deprecations` |
| Morning | Update `namespaces/__init__.py` and `__init__.py` exports |
| Morning | Update `types.py` namespace table and `_RESERVED_NAMESPACES` |
| Afternoon | Run full test suite — fix any regressions |
| Afternoon | Bump version to `2.0.0` in all 5 locations |
| Afternoon | Update `LLM_TOOLKIT_SCHEMA_SOURCE_OF_TRUTH.md` with v2.0 changes |

---

## Key design decisions to carry into the RFC

These are the decisions the RFC must explain with tradeoffs — not just state as facts.

1. **Why `GenAISystem` is an enum, not a free string** — typo-safety, exhaustive pattern matching, direct OTel semconv alignment. Free strings made `ModelInfo.provider` unvalidated and unsearchable.

2. **Why `input_tokens`/`output_tokens` instead of `prompt_tokens`/`completion_tokens`** — OTel semconv `gen_ai.usage.input_tokens` is the standard. Anthropic already uses this naming natively. `prompt` is ambiguous in agent contexts where there is no single "prompt".

3. **Why reasoning content is hashed, not stored** — IP protection (model reasoning is a proprietary artifact), customer data privacy (reasoning may contain sensitive context), storage efficiency. The hash is sufficient for tamper detection and audit trail verification.

4. **Why `CostBreakdown` is a typed object, not `Optional[float]`** — a float is not auditable. Cost attribution in nested agent chains requires per-category breakdown. Cached discounts must be tracked separately. A `total_cost_usd: float` tells you nothing about *why* the cost was what it was.

5. **Why `parent_span_id` instead of embedding child spans** — full OTel span hierarchy compatibility. Any OTel-aware backend (Jaeger, Grafana Tempo, Datadog APM, Honeycomb) can render the tree without any schema knowledge. Embedding creates a non-standard tree that every tool must parse custom.

6. **Why `PricingTier` is stored with the cost record** — provider prices change. A cost record without pricing context is not reproducible six months later. Compliance audits require that cost calculations can be fully reconstructed from the record alone.

7. **Why `CUSTOM` in `GenAISystem` requires `custom_system_name`** — prevents `CUSTOM` from becoming a silent catch-all that collapses observability dashboards into a single unqueriyable bucket. Every `CUSTOM` deployment must be named.

8. **Why `tool_calls` is `List[ToolCall]` (empty list) not `Optional[List[ToolCall]]`** — eliminates the `None` check everywhere in consumer code. A span that made no tool calls has an empty list. This is the same convention OTel uses for span events.
