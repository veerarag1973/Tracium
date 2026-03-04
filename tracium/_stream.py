"""tracium._stream — Internal synchronous event emitter.

This module is the bridge between the tracer's context managers and the
configured export backend.  It is intentionally private — user code should
interact with the tracer, not this module directly.

Flow
----
::

    Span.__exit__
      → _stream.emit_span(span)
        → build SpanPayload
        → build Event(event_type=TRACE_SPAN_COMPLETED, payload=span_payload.to_dict())
        → _active_exporter().export(event)   ← sync

The active exporter is resolved lazily on first use and cached until the
config changes (call :func:`_reset_exporter` after ``configure()``).
"""

from __future__ import annotations

import re
import threading
from typing import Optional

from tracium.config import get_config
from tracium.event import Event, Tags
from tracium.types import EventType

__all__: list[str] = []  # internal — not re-exported from tracium root

# ---------------------------------------------------------------------------
# Source field sanitisation
# ---------------------------------------------------------------------------

_SOURCE_START_RE = re.compile(r"^[a-zA-Z]")
_SOURCE_BODY_RE = re.compile(r"[^a-zA-Z0-9._\-]")
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+")


def _build_source(service_name: str, service_version: str) -> str:
    """Return a valid ``name@version`` source string.

    Sanitise ``service_name`` so it always starts with a letter and contains
    only ``[a-zA-Z0-9._-]``.  Ensures ``service_version`` looks like a semver.
    """
    name = _SOURCE_BODY_RE.sub("-", service_name)
    if not _SOURCE_START_RE.match(name):
        name = "s" + name  # prepend 's' if name starts with a digit/special char
    if not _VERSION_RE.match(service_version):
        service_version = "0.0.0"
    return f"{name}@{service_version}"


# ---------------------------------------------------------------------------
# Exporter resolution
# ---------------------------------------------------------------------------

_exporter_lock = threading.Lock()
_cached_exporter: Optional[object] = None  # SyncExporter protocol instance


def _reset_exporter() -> None:
    """Invalidate the cached exporter so the next emit re-resolves it."""
    global _cached_exporter
    with _exporter_lock:
        _cached_exporter = None


def _active_exporter() -> object:
    """Return the cached exporter, instantiating it from config if necessary."""
    global _cached_exporter
    if _cached_exporter is not None:
        return _cached_exporter
    with _exporter_lock:
        if _cached_exporter is not None:
            return _cached_exporter
        _cached_exporter = _build_exporter()
    return _cached_exporter


def _build_exporter() -> object:
    """Instantiate the correct exporter based on the current config."""
    cfg = get_config()
    name = (cfg.exporter or "console").lower()

    if name == "jsonl":
        from tracium.exporters.jsonl import SyncJSONLExporter  # noqa: PLC0415
        path = cfg.endpoint or "tracium_events.jsonl"
        return SyncJSONLExporter(path)

    if name == "console":
        from tracium.exporters.console import SyncConsoleExporter  # noqa: PLC0415
        return SyncConsoleExporter()

    # Fallback: console
    from tracium.exporters.console import SyncConsoleExporter  # noqa: PLC0415
    return SyncConsoleExporter()


# ---------------------------------------------------------------------------
# Event construction helpers
# ---------------------------------------------------------------------------


def _build_event(
    event_type: EventType,
    payload_dict: dict,
    span_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
) -> Event:
    """Construct a fully-populated :class:`~tracium.event.Event` envelope."""
    cfg = get_config()
    source = _build_source(cfg.service_name, cfg.service_version)

    kwargs: dict = {
        "event_type": event_type,
        "source": source,
        "payload": payload_dict,
    }
    if cfg.org_id:
        kwargs["org_id"] = cfg.org_id
    if span_id:
        kwargs["span_id"] = span_id
    if trace_id:
        kwargs["trace_id"] = trace_id
    if parent_span_id:
        kwargs["parent_span_id"] = parent_span_id

    tags_kwargs: dict = {"env": cfg.env}
    kwargs["tags"] = Tags(**tags_kwargs)

    return Event(**kwargs)


# ---------------------------------------------------------------------------
# Public emit functions (called by _span.py context managers)
# ---------------------------------------------------------------------------


def emit_span(span: object) -> None:
    """Build a ``SpanPayload`` event from *span* and export it.

    Args:
        span: A :class:`~tracium._span.Span` instance.
    """
    # Import here to avoid circular import at module load time.
    from tracium._span import Span  # noqa: PLC0415

    assert isinstance(span, Span)
    payload = span.to_span_payload()
    event_type = (
        EventType.TRACE_SPAN_FAILED if span.status == "error"
        else EventType.TRACE_SPAN_COMPLETED
    )
    event = _build_event(
        event_type=event_type,
        payload_dict=payload.to_dict(),
        span_id=span.span_id,
        trace_id=span.trace_id,
        parent_span_id=span.parent_span_id,
    )
    _dispatch(event)


def emit_agent_step(step: object) -> None:
    """Build an ``AgentStepPayload`` event from *step* and export it."""
    from tracium._span import AgentStepContext  # noqa: PLC0415

    assert isinstance(step, AgentStepContext)
    payload = step.to_agent_step_payload()
    event = _build_event(
        event_type=EventType.TRACE_AGENT_STEP,
        payload_dict=payload.to_dict(),
        span_id=step.span_id,
        trace_id=step.trace_id,
        parent_span_id=step.parent_span_id,
    )
    _dispatch(event)


def emit_agent_run(run: object) -> None:
    """Build an ``AgentRunPayload`` event from *run* and export it."""
    from tracium._span import AgentRunContext  # noqa: PLC0415

    assert isinstance(run, AgentRunContext)
    payload = run.to_agent_run_payload()
    event = _build_event(
        event_type=EventType.TRACE_AGENT_COMPLETED,
        payload_dict=payload.to_dict(),
        trace_id=run.trace_id,
        span_id=run.root_span_id,
    )
    _dispatch(event)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def _dispatch(event: Event) -> None:
    """Export *event* through the active exporter, swallowing all errors."""
    try:
        exporter = _active_exporter()
        exporter.export(event)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        # Never let exporter errors propagate into user code.
        pass
