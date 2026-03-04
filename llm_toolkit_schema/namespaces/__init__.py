"""llm_toolkit_schema.namespaces — Namespace-specific payload dataclasses (v2.0).

Each sub-module provides dataclasses that model the ``payload`` field of
:class:`~llm_toolkit_schema.event.Event` for a given namespace.

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

from llm_toolkit_schema.namespaces.audit import (
    AuditChainTamperedPayload,
    AuditChainVerifiedPayload,
    AuditKeyRotatedPayload,
)
from llm_toolkit_schema.namespaces.cache import (
    CacheEvictedPayload,
    CacheHitPayload,
    CacheMissPayload,
    CacheWrittenPayload,
)
from llm_toolkit_schema.namespaces.cost import (
    CostAttributedPayload,
    CostSessionRecordedPayload,
    CostTokenRecordedPayload,
)
from llm_toolkit_schema.namespaces.diff import (
    DiffComputedPayload,
    DiffRegressionFlaggedPayload,
)
from llm_toolkit_schema.namespaces.eval_ import (
    EvalRegressionDetectedPayload,
    EvalScenarioCompletedPayload,
    EvalScenarioStartedPayload,
    EvalScoreRecordedPayload,
)
from llm_toolkit_schema.namespaces.fence import (
    FenceMaxRetriesExceededPayload,
    FenceRetryTriggeredPayload,
    FenceValidatedPayload,
)
from llm_toolkit_schema.namespaces.guard import GuardPayload
from llm_toolkit_schema.namespaces.prompt import (
    PromptRenderedPayload,
    PromptTemplateLoadedPayload,
    PromptVersionChangedPayload,
)
from llm_toolkit_schema.namespaces.redact import (
    RedactAppliedPayload,
    RedactPhiDetectedPayload,
    RedactPiiDetectedPayload,
)
from llm_toolkit_schema.namespaces.template import (
    TemplateRegisteredPayload,
    TemplateValidationFailedPayload,
    TemplateVariableBoundPayload,
)
from llm_toolkit_schema.namespaces.trace import (
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
    # audit
    "AuditKeyRotatedPayload",
    "AuditChainVerifiedPayload",
    "AuditChainTamperedPayload",
    # cache
    "CacheHitPayload",
    "CacheMissPayload",
    "CacheEvictedPayload",
    "CacheWrittenPayload",
    # cost
    "CostTokenRecordedPayload",
    "CostSessionRecordedPayload",
    "CostAttributedPayload",
    # diff
    "DiffComputedPayload",
    "DiffRegressionFlaggedPayload",
    # eval
    "EvalScoreRecordedPayload",
    "EvalRegressionDetectedPayload",
    "EvalScenarioStartedPayload",
    "EvalScenarioCompletedPayload",
    # fence
    "FenceValidatedPayload",
    "FenceRetryTriggeredPayload",
    "FenceMaxRetriesExceededPayload",
    # guard
    "GuardPayload",
    # prompt
    "PromptRenderedPayload",
    "PromptTemplateLoadedPayload",
    "PromptVersionChangedPayload",
    # redact
    "RedactPiiDetectedPayload",
    "RedactPhiDetectedPayload",
    "RedactAppliedPayload",
    # template
    "TemplateRegisteredPayload",
    "TemplateVariableBoundPayload",
    "TemplateValidationFailedPayload",
    # trace — value objects and payloads
    "GenAISystem",
    "GenAIOperationName",
    "SpanKind",
    "TokenUsage",
    "ModelInfo",
    "CostBreakdown",
    "PricingTier",
    "ToolCall",
    "ReasoningStep",
    "DecisionPoint",
    "SpanPayload",
    "AgentStepPayload",
    "AgentRunPayload",
]