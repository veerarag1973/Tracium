"""tracium._tracer — :class:`Tracer` class and module-level ``tracer`` singleton.

The :class:`Tracer` is the primary entry point for instrumenting code with
Tracium.  Import the module-level singleton ``tracer`` and use its context
managers to create spans and agent traces::

    from tracium import tracer, configure

    configure(exporter="console")

    with tracer.span("chat", model="gpt-4o") as s:
        s.set_attribute("prompt_tokens", 512)

    with tracer.agent_run("research-agent") as run:
        with tracer.agent_step("web-search") as step:
            step.set_attribute("query", "what is RAG?")
        with tracer.agent_step("summarize"):
            pass

All context managers are synchronous (no ``async/await``), work under the
standard Python ``threading`` model, and are re-entrant (each nested span
creates a child span that inherits the parent's ``trace_id``).
"""

from __future__ import annotations

from typing import Any

from tracium._span import (
    AgentRunContextManager,
    AgentStepContextManager,
    SpanContextManager,
)

__all__ = ["Tracer", "tracer"]


class Tracer:
    """The Tracium tracing façade.

    A single module-level instance is created as :data:`tracer` and is the
    recommended way to instrument code.  Creating additional :class:`Tracer`
    instances is supported but shares the same thread-local context stacks.

    All ``span``/``agent_run``/``agent_step`` methods return context managers
    that push the new context onto the thread-local stack on ``__enter__`` and
    pop it (and emit the event) on ``__exit__``.
    """

    # ------------------------------------------------------------------
    # Span API  (Phase 2)
    # ------------------------------------------------------------------

    def span(
        self,
        name: str,
        *,
        model: str | None = None,
        operation: str = "chat",
        attributes: dict[str, Any] | None = None,
    ) -> SpanContextManager:
        """Create a new :class:`~tracium._span.SpanContextManager`.

        Use as a context manager::

            with tracer.span("llm-call", model="gpt-4o") as s:
                s.set_attribute("temperature", 0.7)

        Args:
            name:       Human-readable span name (non-empty string).
            model:      Model name string (e.g. ``"gpt-4o"``).  Used to infer
                        the provider when no integration has set
                        :attr:`~tracium._span.Span.token_usage`.
            operation:  GenAI operation name (default ``"chat"``).  Any
                        :class:`~tracium.namespaces.trace.GenAIOperationName`
                        value or a custom string.
            attributes: Initial key-value attributes.  Additional attributes
                        can be added inside the block via
                        :meth:`~tracium._span.Span.set_attribute`.

        Returns:
            A :class:`~tracium._span.SpanContextManager` that yields a
            :class:`~tracium._span.Span` on ``__enter__``.
        """
        return SpanContextManager(
            name=name,
            model=model,
            operation=operation,
            attributes=attributes,
        )

    # ------------------------------------------------------------------
    # Agent API  (Phase 4)
    # ------------------------------------------------------------------

    def agent_run(self, agent_name: str) -> AgentRunContextManager:
        """Create a root agent-run context manager.

        Use as an outer context that wraps one or more ``agent_step`` calls::

            with tracer.agent_run("my-agent") as run:
                with tracer.agent_step("step-1"):
                    ...

        On exit, emits an
        :data:`~tracium.types.EventType.TRACE_AGENT_COMPLETED` event with
        aggregated totals across all child steps.

        Args:
            agent_name: Name of the agent (non-empty string).

        Returns:
            :class:`~tracium._span.AgentRunContextManager`
        """
        return AgentRunContextManager(agent_name=agent_name)

    def agent_step(
        self,
        step_name: str,
        *,
        operation: str = "invoke_agent",
        attributes: dict[str, Any] | None = None,
    ) -> AgentStepContextManager:
        """Create a single agent-step context manager.

        Must be used inside an ``agent_run`` block::

            with tracer.agent_run("my-agent"):
                with tracer.agent_step("search") as step:
                    step.set_attribute("query", "hello")

        On exit, emits an
        :data:`~tracium.types.EventType.TRACE_AGENT_STEP` event.

        Args:
            step_name:  Human-readable step name.
            operation:  GenAI operation name (default ``"invoke_agent"``).
            attributes: Initial key-value attributes.

        Returns:
            :class:`~tracium._span.AgentStepContextManager`

        Raises:
            RuntimeError: If called outside an ``agent_run`` context.
        """
        return AgentStepContextManager(
            step_name=step_name,
            operation=operation,
            attributes=attributes,
        )


# ---------------------------------------------------------------------------
# Module-level singleton — ``from tracium import tracer``
# ---------------------------------------------------------------------------

#: The default :class:`Tracer` singleton.
#:
#: Import this directly for convenience::
#:
#:     from tracium import tracer
#:     with tracer.span("my-span"):
#:         ...
tracer: Tracer = Tracer()
