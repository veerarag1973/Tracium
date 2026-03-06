# Namespace Payload Catalogue

AgentOBS ships typed payload dataclasses for eleven standard namespaces. Every
namespace payload is a Python dataclass that can be serialised to/from a plain
`dict` for storage in `Event.payload`.

## Namespaces

- [trace](trace.md)
- [cost](cost.md)
- [cache](cache.md)
- [diff](diff.md)
- [eval](eval.md)
- [fence](fence.md)
- [guard](guard.md)
- [prompt](prompt.md)
- [redact_ns](redact_ns.md)
- [template](template.md)
- [audit](audit.md)

## Namespace quick-reference

| Namespace prefix | Module | Key payload classes |
|------------------|--------|---------------------|
| `llm.trace.*` | `agentobs.namespaces.trace` | `SpanPayload`, `AgentStepPayload`, `AgentRunPayload` |
| `llm.cost.*` | `agentobs.namespaces.cost` | `CostTokenRecordedPayload`, `CostSessionRecordedPayload`, `CostAttributedPayload` |
| `llm.cache.*` | `agentobs.namespaces.cache` | `CacheHitPayload`, `CacheMissPayload`, `CacheEvictedPayload`, `CacheWrittenPayload` |
| `llm.diff.*` | `agentobs.namespaces.diff` | `DiffComputedPayload`, `DiffRegressionFlaggedPayload` |
| `llm.eval.*` | `agentobs.namespaces.eval_` | `EvalScoreRecordedPayload`, `EvalRegressionDetectedPayload`, `EvalScenarioStartedPayload`, `EvalScenarioCompletedPayload` |
| `llm.fence.*` | `agentobs.namespaces.fence` | `FenceValidatedPayload`, `FenceRetryTriggeredPayload`, `FenceMaxRetriesExceededPayload` |
| `llm.guard.*` | `agentobs.namespaces.guard` | `GuardPayload` |
| `llm.prompt.*` | `agentobs.namespaces.prompt` | `PromptRenderedPayload`, `PromptTemplateLoadedPayload`, `PromptVersionChangedPayload` |
| `llm.redact.*` | `agentobs.namespaces.redact` | `RedactPiiDetectedPayload`, `RedactPhiDetectedPayload`, `RedactAppliedPayload` |
| `llm.template.*` | `agentobs.namespaces.template` | `TemplateRegisteredPayload`, `TemplateVariableBoundPayload`, `TemplateValidationFailedPayload` |
| `llm.audit.*` | `agentobs.namespaces.audit` | `AuditKeyRotatedPayload`, `AuditChainVerifiedPayload`, `AuditChainTamperedPayload` |

## Using a namespace payload

```python
from agentobs import Event, EventType
from agentobs.namespaces.trace import SpanPayload, TokenUsage, ModelInfo, GenAISystem

token_usage = TokenUsage(input_tokens=512, output_tokens=128, total_tokens=640)
model_info  = ModelInfo(system=GenAISystem.OPENAI, name="gpt-4o")

payload = SpanPayload(
    span_name="chat_completion",
    status="ok",
    duration_ms=340.5,
    token_usage=token_usage.to_dict(),
    model_info=model_info.to_dict(),
)

event = Event(
    event_type=EventType.TRACE_SPAN_COMPLETED,
    source="my-app@1.0.0",
    org_id="org_01HX",
    payload=payload.to_dict(),
)
```
