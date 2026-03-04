"""tracium.integrations.langchain — LangChain callback handler.

Provides :class:`LLMSchemaCallbackHandler`, a LangChain-compatible
callback handler that records LLM and tool-call activity as Tracium events.

Usage::

    from tracium.integrations.langchain import LLMSchemaCallbackHandler

    handler = LLMSchemaCallbackHandler(source="my-app", org_id="org-1")
    chain = SomeChain(callbacks=[handler])
    chain.run("What is 2+2?")

    for event in handler.events:
        print(event.to_json())
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Union
from uuid import UUID

from tracium.event import Event
from tracium.ulid import generate as gen_ulid

__all__ = [
    "LLMSchemaCallbackHandler",
]

# ---------------------------------------------------------------------------
# Module resolver
# ---------------------------------------------------------------------------


def _require_langchain() -> Any:  # noqa: ANN401
    """Return the LangChain callbacks module (``langchain_core.callbacks`` or
    ``langchain.callbacks``).

    Tries ``langchain_core.callbacks`` first (preferred, modern API), then
    falls back to the legacy ``langchain.callbacks`` module.

    Raises:
        ImportError: If neither ``langchain_core`` nor ``langchain`` is installed.
    """
    # Try modern langchain_core first.  Import the parent module first so that
    # a None sentinel in sys.modules propagates as ImportError correctly.
    try:
        import langchain_core  # noqa: PLC0415
        import langchain_core.callbacks  # noqa: PLC0415
        import sys
        return sys.modules["langchain_core.callbacks"]
    except ImportError:
        pass
    # Fall back to legacy langchain package.
    try:
        import langchain  # noqa: PLC0415
        import langchain.callbacks  # noqa: PLC0415
        import sys
        return sys.modules["langchain.callbacks"]
    except ImportError:
        pass
    raise ImportError(
        "LangChain package is required for the tracium LangChain integration.\n"
        "Install it with: pip install 'tracium[langchain]'"
    )


# ---------------------------------------------------------------------------
# Callback handler
# ---------------------------------------------------------------------------


class LLMSchemaCallbackHandler:
    """LangChain callback handler that emits Tracium events.

    Compatible with both ``langchain_core`` and legacy ``langchain`` SDK
    versions.  Events are accumulated in :attr:`events` and optionally
    forwarded to an async exporter.

    Args:
        source:   Value for ``Event.source`` (e.g. ``"my-llm-app@1.0.0"``).
        org_id:   Optional organisation identifier.
        exporter: Optional async exporter; must have an ``export(event)``
                  coroutine method.  When the event loop is running, export is
                  scheduled as a task; otherwise the call is silently skipped.

    Attributes:
        events: List of all :class:`~tracium.event.Event` objects emitted by
                this handler in chronological order.
    """

    def __init__(
        self,
        source: str,
        *,
        org_id: Optional[str] = None,
        exporter: Optional[Any] = None,
    ) -> None:
        self._source = source
        self._org_id = org_id
        self._exporter = exporter
        self.events: List[Event] = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_event(self, event_type: str, payload: Dict[str, Any]) -> Event:
        """Create a Tracium event and optionally schedule async export.

        Args:
            event_type: Dotted event type string.
            payload:    Event payload dict.

        Returns:
            The newly created :class:`~tracium.event.Event`.
        """
        event = Event(
            event_type=event_type,
            source=self._source,
            org_id=self._org_id,
            payload=payload,
            event_id=gen_ulid(),
        )
        self.events.append(event)

        if self._exporter is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._exporter.export(event))
            except RuntimeError:
                pass  # no running event loop

        return event

    # ------------------------------------------------------------------
    # LangChain callback interface
    # ------------------------------------------------------------------

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when an LLM invocation begins.

        Args:
            serialized: Serialised LLM config dict (contains ``id`` list).
            prompts:    List of prompt strings being sent to the LLM.
            run_id:     LangChain run identifier.
            **kwargs:   Additional keyword arguments (ignored).
        """
        llm_name = ""
        if serialized and "id" in serialized and serialized["id"]:
            llm_name = str(serialized["id"][-1])
        self._make_event(
            "llm.trace.span.started",
            {
                "llm_name": llm_name,
                "prompt_count": len(prompts),
                "run_id": str(run_id) if run_id is not None else None,
            },
        )

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when an LLM invocation completes.

        Args:
            response: LangChain ``LLMResult`` object with ``llm_output`` attribute.
            run_id:   LangChain run identifier.
            **kwargs: Additional keyword arguments (ignored).
        """
        llm_output = getattr(response, "llm_output", None)
        prompt_tokens: Optional[int] = None
        completion_tokens: Optional[int] = None
        total_tokens: Optional[int] = None

        if isinstance(llm_output, dict):
            token_usage = llm_output.get("token_usage") or {}
            if isinstance(token_usage, dict):
                prompt_tokens = token_usage.get("prompt_tokens")
                completion_tokens = token_usage.get("completion_tokens")
                total_tokens = token_usage.get("total_tokens")

        self._make_event(
            "llm.trace.span.completed",
            {
                "run_id": str(run_id) if run_id is not None else None,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
        )

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when an LLM invocation raises an error.

        Args:
            error:    The exception that was raised.
            run_id:   LangChain run identifier.
            **kwargs: Additional keyword arguments (ignored).
        """
        self._make_event(
            "llm.trace.span.error",
            {
                "run_id": str(run_id) if run_id is not None else None,
                "error": str(error),
                "error_type": type(error).__name__,
            },
        )

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a tool invocation begins.

        Args:
            serialized: Serialised tool config dict (usually has ``"name"`` key).
            input_str:  String input passed to the tool.
            run_id:     LangChain run identifier.
            **kwargs:   Additional keyword arguments (ignored).
        """
        tool_name = serialized.get("name", "") if serialized else ""
        self._make_event(
            "llm.trace.tool_call.started",
            {
                "tool_name": tool_name,
                "input": input_str,
                "run_id": str(run_id) if run_id is not None else None,
            },
        )

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a tool invocation completes.

        Args:
            output:   String output returned by the tool.
            run_id:   LangChain run identifier.
            **kwargs: Additional keyword arguments (ignored).
        """
        self._make_event(
            "llm.trace.tool_call.completed",
            {
                "run_id": str(run_id) if run_id is not None else None,
                "output": str(output)[:1024] if output else None,
            },
        )

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a tool invocation raises an error.

        Args:
            error:    The exception that was raised.
            run_id:   LangChain run identifier.
            **kwargs: Additional keyword arguments (ignored).
        """
        self._make_event(
            "llm.trace.tool_call.error",
            {
                "run_id": str(run_id) if run_id is not None else None,
                "error": str(error),
                "error_type": type(error).__name__,
            },
        )

    def clear_events(self) -> None:
        """Remove all accumulated events from :attr:`events`."""
        self.events.clear()

    # ------------------------------------------------------------------
    # dunder
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"LLMSchemaCallbackHandler("
            f"source={self._source!r}, "
            f"events={len(self.events)})"
        )
