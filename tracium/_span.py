"""tracium._span — Span, SpanContextManager, and agent context managers.

Provides the runtime tracing primitives that back ``tracer.span()``,
``tracer.agent_run()``, and ``tracer.agent_step()``.

Design notes
------------
* **Thread-local stacks** keep parent-child relationships correct across
  concurrent threads without global locking.
* **OTel-compatible IDs** — ``span_id`` is 8 random bytes (16 hex chars),
  ``trace_id`` is 16 random bytes (32 hex chars), matching the OTel wire
  format expected by :class:`~tracium.namespaces.trace.SpanPayload`.
* **Zero external dependencies** — stdlib only (``os``, ``time``,
  ``threading``, ``types``).
"""

from __future__ import annotations

import os
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, Dict, List, Optional, Type, Union

from tracium.namespaces.trace import (
    AgentRunPayload,
    AgentStepPayload,
    CostBreakdown,
    DecisionPoint,
    GenAIOperationName,
    GenAISystem,
    ModelInfo,
    ReasoningStep,
    SpanKind,
    SpanPayload,
    TokenUsage,
    ToolCall,
)

__all__ = [
    "Span",
    "SpanContextManager",
    "AgentRunContext",
    "AgentRunContextManager",
    "AgentStepContext",
    "AgentStepContextManager",
]

# ---------------------------------------------------------------------------
# ID generation helpers
# ---------------------------------------------------------------------------


def _span_id() -> str:
    """Generate an OTel-compatible span ID: 8 random bytes → 16 lowercase hex chars."""
    return os.urandom(8).hex()


def _trace_id() -> str:
    """Generate an OTel-compatible trace ID: 16 random bytes → 32 lowercase hex chars."""
    return os.urandom(16).hex()


def _now_ns() -> int:
    """Current time as integer nanoseconds since the Unix epoch."""
    return time.time_ns()


# ---------------------------------------------------------------------------
# Thread-local context stacks
# ---------------------------------------------------------------------------

_local = threading.local()


def _span_stack() -> List["Span"]:
    """Return the per-thread span stack, creating it on first access."""
    if not hasattr(_local, "span_stack"):
        _local.span_stack = []
    return _local.span_stack


def _run_stack() -> List["AgentRunContext"]:
    """Return the per-thread agent-run stack, creating it on first access."""
    if not hasattr(_local, "run_stack"):
        _local.run_stack = []
    return _local.run_stack


def _step_list() -> List["AgentStepContext"]:
    """Return the per-thread step accumulator for the active agent run."""
    if not hasattr(_local, "step_list"):
        _local.step_list = []
    return _local.step_list


# ---------------------------------------------------------------------------
# Span
# ---------------------------------------------------------------------------


@dataclass
class Span:
    """Mutable span record accumulated during a ``with tracer.span(...)`` block.

    Create via :class:`SpanContextManager` (i.e. ``tracer.span(...)``).
    Direct construction is supported for testing.

    Auto-populated fields
    ----------------------
    ``span_id``, ``trace_id``, and ``start_ns`` are assigned by
    :class:`SpanContextManager.__enter__`; do not set them manually unless
    you need custom IDs for testing.

    Attributes:
        name:            Human-readable span name.
        span_id:         16 lowercase hex chars (OTel span ID).
        trace_id:        32 lowercase hex chars (OTel trace ID).
        parent_span_id:  Parent span ID if nested; ``None`` for root spans.
        agent_run_id:    ULID of the enclosing agent run, if any.
        model:           Model name string (e.g. ``"gpt-4o"``).
        operation:       GenAI operation name (default ``"chat"``).
        attributes:      Arbitrary key-value metadata set by the user.
        start_ns:        Start time as nanoseconds since Unix epoch.
        end_ns:          End time (set on :meth:`end`).
        duration_ms:     Computed duration in milliseconds.
        status:          ``"ok"`` or ``"error"`` or ``"timeout"``.
        error:           Error message if ``status == "error"``.
        error_type:      Exception class name if ``status == "error"``.
        token_usage:     Optional token counts (set by provider integrations).
        cost:            Optional cost breakdown (set by provider integrations).
    """

    name: str
    span_id: str = field(default_factory=_span_id)
    trace_id: str = field(default_factory=_trace_id)
    parent_span_id: Optional[str] = None
    agent_run_id: Optional[str] = None
    model: Optional[str] = None
    operation: str = "chat"
    attributes: Dict[str, Any] = field(default_factory=dict)
    start_ns: int = field(default_factory=_now_ns)
    end_ns: Optional[int] = None
    duration_ms: Optional[float] = None
    status: str = "ok"
    error: Optional[str] = None
    error_type: Optional[str] = None
    token_usage: Optional[TokenUsage] = None
    cost: Optional[CostBreakdown] = None
    tool_calls: List[ToolCall] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Mutation methods (call from inside ``with tracer.span(...) as s:``)
    # ------------------------------------------------------------------

    def set_attribute(self, key: str, value: Any) -> None:
        """Add or update a key-value attribute on this span.

        Args:
            key:   Attribute name (non-empty string).
            value: Attribute value (any JSON-serialisable type).
        """
        if not isinstance(key, str) or not key:
            raise ValueError("set_attribute: key must be a non-empty string")
        self.attributes[key] = value

    def record_error(self, exc: Exception) -> None:
        """Record an exception on this span, setting ``status = "error"``.

        Args:
            exc: The exception that caused the failure.
        """
        self.status = "error"
        self.error = str(exc)
        self.error_type = type(exc).__qualname__

    def set_token_usage(self, token_usage: TokenUsage) -> None:
        """Attach token usage data (called by provider integrations)."""
        self.token_usage = token_usage

    def set_cost(self, cost: CostBreakdown) -> None:
        """Attach cost breakdown data (called by provider integrations)."""
        self.cost = cost

    # ------------------------------------------------------------------
    # Internal lifecycle
    # ------------------------------------------------------------------

    def end(self) -> None:
        """Finalise the span by recording the end time and computing duration."""
        if self.end_ns is None:
            self.end_ns = _now_ns()
            self.duration_ms = (self.end_ns - self.start_ns) / 1_000_000.0

    def to_span_payload(self) -> SpanPayload:
        """Serialise this span to a :class:`~tracium.namespaces.trace.SpanPayload`.

        Called internally by :class:`SpanContextManager.__exit__` just before
        event emission.
        """
        end_ns = self.end_ns if self.end_ns is not None else _now_ns()
        duration_ms = (end_ns - self.start_ns) / 1_000_000.0

        # Resolve ModelInfo from the model name string.
        model_info: Optional[ModelInfo] = None
        if self.model:
            model_info = _resolve_model_info(self.model)

        # Resolve operation enum.
        try:
            operation: Union[GenAIOperationName, str] = GenAIOperationName(self.operation)
        except ValueError:
            operation = self.operation

        return SpanPayload(
            span_id=self.span_id,
            trace_id=self.trace_id,
            span_name=self.name,
            operation=operation,
            span_kind=SpanKind.CLIENT,
            status=self.status,
            start_time_unix_nano=self.start_ns,
            end_time_unix_nano=end_ns,
            duration_ms=duration_ms,
            parent_span_id=self.parent_span_id,
            agent_run_id=self.agent_run_id,
            model=model_info,
            token_usage=self.token_usage,
            cost=self.cost,
            tool_calls=list(self.tool_calls),
            error=self.error,
            error_type=self.error_type,
            attributes=self.attributes if self.attributes else None,
        )


# ---------------------------------------------------------------------------
# SpanContextManager
# ---------------------------------------------------------------------------


class SpanContextManager:
    """Context manager returned by :meth:`~tracium._tracer.Tracer.span`.

    Usage::

        with tracer.span("my-llm-call", model="gpt-4o") as span:
            span.set_attribute("prompt_length", 256)
            # ... call LLM ...
        # → SpanPayload event emitted on exit

    The :class:`Span` instance is bound to the ``as`` target and is also
    pushed onto the thread-local span stack so nested spans can inherit the
    ``trace_id``.
    """

    def __init__(
        self,
        name: str,
        model: Optional[str] = None,
        operation: str = "chat",
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._name = name
        self._model = model
        self._operation = operation
        self._initial_attributes = dict(attributes or {})
        self._span: Optional[Span] = None

    # ------------------------------------------------------------------
    # Context manager protocol
    # ------------------------------------------------------------------

    def __enter__(self) -> Span:
        stack = _span_stack()

        # Inherit trace_id and parent_span_id from the enclosing span.
        if stack:
            parent = stack[-1]
            trace_id = parent.trace_id
            parent_span_id = parent.span_id
        else:
            trace_id = _trace_id()
            parent_span_id = None

        # Inherit agent_run_id from the enclosing run context.
        run_stack = _run_stack()
        agent_run_id = run_stack[-1].agent_run_id if run_stack else None

        self._span = Span(
            name=self._name,
            span_id=_span_id(),
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            agent_run_id=agent_run_id,
            model=self._model,
            operation=self._operation,
            attributes=dict(self._initial_attributes),
            start_ns=_now_ns(),
        )
        stack.append(self._span)
        return self._span

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> bool:
        assert self._span is not None, "SpanContextManager.__exit__ called before __enter__"

        # Record any unhandled exception on the span.
        if exc_val is not None and self._span.status == "ok":
            self._span.record_error(exc_val)

        self._span.end()

        # Pop from the span stack.
        stack = _span_stack()
        if stack and stack[-1] is self._span:
            stack.pop()

        # Emit the event.
        try:
            from tracium import _stream  # noqa: PLC0415
            _stream.emit_span(self._span)
        except Exception:  # noqa: BLE001
            # Never let emission failures propagate into user code.
            pass

        # Do NOT suppress the original exception.
        return False


# ---------------------------------------------------------------------------
# Agent step context
# ---------------------------------------------------------------------------


@dataclass
class AgentStepContext:
    """Mutable record accumulated during ``with tracer.agent_step(...)``."""

    step_name: str
    agent_run_id: str
    step_index: int
    span_id: str = field(default_factory=_span_id)
    trace_id: str = field(default_factory=_trace_id)
    parent_span_id: Optional[str] = None
    operation: str = "invoke_agent"
    start_ns: int = field(default_factory=_now_ns)
    end_ns: Optional[int] = None
    duration_ms: Optional[float] = None
    status: str = "ok"
    error: Optional[str] = None
    error_type: Optional[str] = None
    model: Optional[str] = None
    token_usage: Optional[TokenUsage] = None
    cost: Optional[CostBreakdown] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    reasoning_steps: List[ReasoningStep] = field(default_factory=list)
    decision_points: List[DecisionPoint] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def set_attribute(self, key: str, value: Any) -> None:
        if not isinstance(key, str) or not key:
            raise ValueError("set_attribute: key must be a non-empty string")
        self.attributes[key] = value

    def record_error(self, exc: Exception) -> None:
        self.status = "error"
        self.error = str(exc)
        self.error_type = type(exc).__qualname__

    def end(self) -> None:
        if self.end_ns is None:
            self.end_ns = _now_ns()
            self.duration_ms = (self.end_ns - self.start_ns) / 1_000_000.0

    def to_agent_step_payload(self) -> AgentStepPayload:
        end_ns = self.end_ns if self.end_ns is not None else _now_ns()
        duration_ms = (end_ns - self.start_ns) / 1_000_000.0
        try:
            operation: Union[GenAIOperationName, str] = GenAIOperationName(self.operation)
        except ValueError:
            operation = self.operation
        return AgentStepPayload(
            agent_run_id=self.agent_run_id,
            step_index=self.step_index,
            span_id=self.span_id,
            trace_id=self.trace_id,
            operation=operation,
            tool_calls=list(self.tool_calls),
            reasoning_steps=list(self.reasoning_steps),
            decision_points=list(self.decision_points),
            status=self.status,
            start_time_unix_nano=self.start_ns,
            end_time_unix_nano=end_ns,
            duration_ms=duration_ms,
            parent_span_id=self.parent_span_id,
            model=_resolve_model_info(self.model) if self.model else None,
            token_usage=self.token_usage,
            cost=self.cost,
            error=self.error,
            error_type=self.error_type,
        )


class AgentStepContextManager:
    """Context manager returned by :meth:`~tracium._tracer.Tracer.agent_step`."""

    def __init__(
        self,
        step_name: str,
        operation: str = "invoke_agent",
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._step_name = step_name
        self._operation = operation
        self._initial_attributes = dict(attributes or {})
        self._ctx: Optional[AgentStepContext] = None

    def __enter__(self) -> AgentStepContext:
        run_stack = _run_stack()
        if not run_stack:
            raise RuntimeError(
                "tracer.agent_step() must be used inside a tracer.agent_run() context"
            )
        run = run_stack[-1]

        # Inherit trace_id + parent from any enclosing span.
        span_stack = _span_stack()
        if span_stack:
            parent = span_stack[-1]
            trace_id = parent.trace_id
            parent_span_id = parent.span_id
        else:
            trace_id = run.trace_id
            parent_span_id = None

        step_index = run.next_step_index()

        self._ctx = AgentStepContext(
            step_name=self._step_name,
            agent_run_id=run.agent_run_id,
            step_index=step_index,
            span_id=_span_id(),
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            operation=self._operation,
            start_ns=_now_ns(),
            attributes=dict(self._initial_attributes),
        )
        return self._ctx

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> bool:
        assert self._ctx is not None

        if exc_val is not None and self._ctx.status == "ok":
            self._ctx.record_error(exc_val)
        self._ctx.end()

        # Register step with the parent run context.
        run_stack = _run_stack()
        if run_stack:
            run_stack[-1].record_step(self._ctx)

        # Emit agent step event.
        try:
            from tracium import _stream  # noqa: PLC0415
            _stream.emit_agent_step(self._ctx)
        except Exception:  # noqa: BLE001
            pass

        return False


# ---------------------------------------------------------------------------
# Agent run context
# ---------------------------------------------------------------------------


@dataclass
class AgentRunContext:
    """Mutable record accumulated during ``with tracer.agent_run(...)``."""

    agent_name: str
    agent_run_id: str = field(default_factory=_span_id)  # 16 hex chars
    trace_id: str = field(default_factory=_trace_id)
    root_span_id: str = field(default_factory=_span_id)
    start_ns: int = field(default_factory=_now_ns)
    end_ns: Optional[int] = None
    duration_ms: Optional[float] = None
    status: str = "ok"
    error: Optional[str] = None
    termination_reason: Optional[str] = None
    _step_count: int = field(default=0, init=False, repr=False)
    _steps: List[AgentStepContext] = field(default_factory=list, init=False, repr=False)

    def next_step_index(self) -> int:
        idx = self._step_count
        self._step_count += 1
        return idx

    def record_step(self, step: AgentStepContext) -> None:
        self._steps.append(step)

    def record_error(self, exc: Exception) -> None:
        self.status = "error"
        self.error = str(exc)

    def end(self) -> None:
        if self.end_ns is None:
            self.end_ns = _now_ns()
            self.duration_ms = (self.end_ns - self.start_ns) / 1_000_000.0

    def to_agent_run_payload(self) -> AgentRunPayload:
        end_ns = self.end_ns if self.end_ns is not None else _now_ns()
        duration_ms = (end_ns - self.start_ns) / 1_000_000.0

        # Aggregate token usage and cost across all steps.
        total_input = 0
        total_output = 0
        total_tokens = 0
        total_in_cost = 0.0
        total_out_cost = 0.0
        total_model_calls = 0
        total_tool_calls = 0
        for step in self._steps:
            if step.token_usage:
                total_input += step.token_usage.input_tokens
                total_output += step.token_usage.output_tokens
                total_tokens += step.token_usage.total_tokens
                total_model_calls += 1
            total_tool_calls += len(step.tool_calls)
            if step.cost:
                total_in_cost += step.cost.input_cost_usd
                total_out_cost += step.cost.output_cost_usd

        total_token_usage = TokenUsage(
            input_tokens=total_input,
            output_tokens=total_output,
            total_tokens=total_tokens,
        )
        total_cost = CostBreakdown(
            input_cost_usd=total_in_cost,
            output_cost_usd=total_out_cost,
            total_cost_usd=total_in_cost + total_out_cost,
        )

        return AgentRunPayload(
            agent_run_id=self.agent_run_id,
            agent_name=self.agent_name,
            trace_id=self.trace_id,
            root_span_id=self.root_span_id,
            total_steps=len(self._steps),
            total_model_calls=total_model_calls,
            total_tool_calls=total_tool_calls,
            total_token_usage=total_token_usage,
            total_cost=total_cost,
            status=self.status,
            start_time_unix_nano=self.start_ns,
            end_time_unix_nano=end_ns,
            duration_ms=duration_ms,
            termination_reason=self.termination_reason,
        )


class AgentRunContextManager:
    """Context manager returned by :meth:`~tracium._tracer.Tracer.agent_run`."""

    def __init__(self, agent_name: str) -> None:
        self._agent_name = agent_name
        self._ctx: Optional[AgentRunContext] = None

    def __enter__(self) -> AgentRunContext:
        self._ctx = AgentRunContext(
            agent_name=self._agent_name,
            agent_run_id=_span_id(),
            trace_id=_trace_id(),
            root_span_id=_span_id(),
            start_ns=_now_ns(),
        )
        _run_stack().append(self._ctx)
        return self._ctx

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> bool:
        assert self._ctx is not None

        if exc_val is not None and self._ctx.status == "ok":
            self._ctx.record_error(exc_val)
        self._ctx.end()

        run_stack = _run_stack()
        if run_stack and run_stack[-1] is self._ctx:
            run_stack.pop()

        try:
            from tracium import _stream  # noqa: PLC0415
            _stream.emit_agent_run(self._ctx)
        except Exception:  # noqa: BLE001
            pass

        return False


# ---------------------------------------------------------------------------
# Helper: model name → ModelInfo
# ---------------------------------------------------------------------------


def _resolve_model_info(model_name: str) -> ModelInfo:
    """Infer :class:`~tracium.namespaces.trace.ModelInfo` from a model name string.

    Uses prefix heuristics (``"claude-"`` → Anthropic, etc.) with
    :attr:`~tracium.namespaces.trace.GenAISystem.OPENAI` as the fallback.
    """
    name_lower = model_name.lower()
    if name_lower.startswith("claude"):
        system = GenAISystem.ANTHROPIC
    elif name_lower.startswith("gemini"):
        system = GenAISystem.VERTEX_AI
    elif name_lower.startswith("command"):
        system = GenAISystem.COHERE
    elif name_lower.startswith("mistral") or name_lower.startswith("mixtral"):
        system = GenAISystem.MISTRAL_AI
    elif name_lower.startswith("llama") or name_lower.startswith("phi") or name_lower.startswith("qwen"):
        system = GenAISystem.OLLAMA
    else:
        system = GenAISystem.OPENAI
    return ModelInfo(system=system, name=model_name)
