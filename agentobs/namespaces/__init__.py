"""agentobs.namespaces — Namespace-specific payload dataclasses (v2.0).

Each sub-module provides dataclasses that model the ``payload`` field of
:class:`~agentobs.event.Event` for a given namespace.

All payload classes share the same contract:

* ``to_dict() -> dict`` — serialise to a plain dict for ``Event.payload``.
* ``from_dict(data) -> cls`` — reconstruct from a plain dict.
* ``__post_init__`` — validates every field at construction time.

Sub-modules
-----------
audit
    :class:`AuditKeyRotatedPayload`, :class:`AuditChainVerifiedPayload`,
    :class:`AuditChainTamperedPayload`
cache
    :class:`CacheHitPayload`, :class:`CacheMissPayload`,
    :class:`CacheEvictedPayload`, :class:`CacheWrittenPayload`
cost
    :class:`CostTokenRecordedPayload`, :class:`CostSessionRecordedPayload`,
    :class:`CostAttributedPayload`
diff
    :class:`DiffComputedPayload`, :class:`DiffRegressionFlaggedPayload`
eval_
    :class:`EvalScoreRecordedPayload`, :class:`EvalRegressionDetectedPayload`,
    :class:`EvalScenarioStartedPayload`, :class:`EvalScenarioCompletedPayload`
fence
    :class:`FenceValidatedPayload`, :class:`FenceRetryTriggeredPayload`,
    :class:`FenceMaxRetriesExceededPayload`
guard
    :class:`GuardPayload`
prompt
    :class:`PromptRenderedPayload`, :class:`PromptTemplateLoadedPayload`,
    :class:`PromptVersionChangedPayload`
redact
    :class:`RedactPiiDetectedPayload`, :class:`RedactPhiDetectedPayload`,
    :class:`RedactAppliedPayload`
template
    :class:`TemplateRegisteredPayload`, :class:`TemplateVariableBoundPayload`,
    :class:`TemplateValidationFailedPayload`
trace
    :class:`GenAISystem`, :class:`GenAIOperationName`, :class:`SpanKind`,
    :class:`TokenUsage`, :class:`ModelInfo`, :class:`CostBreakdown`,
    :class:`PricingTier`, :class:`ToolCall`, :class:`ReasoningStep`,
    :class:`DecisionPoint`, :class:`SpanPayload`, :class:`AgentStepPayload`,
    :class:`AgentRunPayload`
"""

from agentobs.namespaces.audit import (
    AuditChainTamperedPayload,
    AuditChainVerifiedPayload,
    AuditKeyRotatedPayload,
)
from agentobs.namespaces.cache import (
    CacheEvictedPayload,
    CacheHitPayload,
    CacheMissPayload,
    CacheWrittenPayload,
)
from agentobs.namespaces.cost import (
    CostAttributedPayload,
    CostSessionRecordedPayload,
    CostTokenRecordedPayload,
)
from agentobs.namespaces.diff import (
    DiffComputedPayload,
    DiffRegressionFlaggedPayload,
)
from agentobs.namespaces.eval_ import (
    EvalRegressionDetectedPayload,
    EvalScenarioCompletedPayload,
    EvalScenarioStartedPayload,
    EvalScoreRecordedPayload,
)
from agentobs.namespaces.fence import (
    FenceMaxRetriesExceededPayload,
    FenceRetryTriggeredPayload,
    FenceValidatedPayload,
)
from agentobs.namespaces.guard import GuardPayload
from agentobs.namespaces.prompt import (
    PromptRenderedPayload,
    PromptTemplateLoadedPayload,
    PromptVersionChangedPayload,
)
from agentobs.namespaces.redact import (
    RedactAppliedPayload,
    RedactPhiDetectedPayload,
    RedactPiiDetectedPayload,
)
from agentobs.namespaces.template import (
    TemplateRegisteredPayload,
    TemplateValidationFailedPayload,
    TemplateVariableBoundPayload,
)
from agentobs.namespaces.trace import (
    AgentRunPayload,
    AgentStepPayload,
    CostBreakdown,
    DecisionPoint,
    GenAIOperationName,
    GenAISystem,
    ModelInfo,
    PricingTier,
    ReasoningStep,
    SpanKind,
    SpanPayload,
    TokenUsage,
    ToolCall,
)

__all__: list = [
    "AgentRunPayload",
    "AgentStepPayload",
    "AuditChainTamperedPayload",
    "AuditChainVerifiedPayload",
    # audit
    "AuditKeyRotatedPayload",
    "CacheEvictedPayload",
    # cache
    "CacheHitPayload",
    "CacheMissPayload",
    "CacheWrittenPayload",
    "CostAttributedPayload",
    "CostBreakdown",
    "CostSessionRecordedPayload",
    # cost
    "CostTokenRecordedPayload",
    "DecisionPoint",
    # diff
    "DiffComputedPayload",
    "DiffRegressionFlaggedPayload",
    "EvalRegressionDetectedPayload",
    "EvalScenarioCompletedPayload",
    "EvalScenarioStartedPayload",
    # eval
    "EvalScoreRecordedPayload",
    "FenceMaxRetriesExceededPayload",
    "FenceRetryTriggeredPayload",
    # fence
    "FenceValidatedPayload",
    "GenAIOperationName",
    # trace — value objects and payloads
    "GenAISystem",
    # guard
    "GuardPayload",
    "ModelInfo",
    "PricingTier",
    # prompt
    "PromptRenderedPayload",
    "PromptTemplateLoadedPayload",
    "PromptVersionChangedPayload",
    "ReasoningStep",
    "RedactAppliedPayload",
    "RedactPhiDetectedPayload",
    # redact
    "RedactPiiDetectedPayload",
    "SpanKind",
    "SpanPayload",
    # template
    "TemplateRegisteredPayload",
    "TemplateValidationFailedPayload",
    "TemplateVariableBoundPayload",
    "TokenUsage",
    "ToolCall",
]
