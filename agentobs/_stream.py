"""agentobs._stream — Internal synchronous event emitter.

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
import warnings

from agentobs.config import get_config
from agentobs.event import Event, Tags
from agentobs.types import EventType

__all__: list[str] = []  # internal — not re-exported from agentobs root

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
_cached_exporter: object | None = None  # SyncExporter protocol instance

# ---------------------------------------------------------------------------
# Signing chain state
# ---------------------------------------------------------------------------

_sign_lock = threading.Lock()
_prev_signed_event: Event | None = None  # last event in the HMAC chain


def _handle_export_error(exc: Exception) -> None:
    """Apply the configured ``on_export_error`` policy for *exc*.

    Policies:

    - ``"drop"``  — silently discard the error (opt-in to original behaviour).
    - ``"warn"``  — emit a :mod:`warnings` ``UserWarning`` (default).
    - ``"raise"`` — re-raise the exception into caller code.
    """
    try:
        policy = get_config().on_export_error
    except Exception:
        policy = "warn"  # safe fallback if config itself is broken

    if policy == "raise":
        raise exc
    if policy == "warn":
        warnings.warn(
            f"agentobs export error ({type(exc).__name__}): {exc}",
            stacklevel=3,
        )
    # "drop": discard silently


def _reset_exporter() -> None:
    """Invalidate the cached exporter and reset the HMAC signing chain."""
    global _cached_exporter, _prev_signed_event  # noqa: PLW0603
    with _exporter_lock:
        if _cached_exporter is not None:
            # Flush + close any open file handles before discarding the exporter.
            try:
                if hasattr(_cached_exporter, "close"):
                    _cached_exporter.close()  # type: ignore[union-attr]
            except Exception as exc:
                _handle_export_error(exc)
        _cached_exporter = None
    with _sign_lock:
        _prev_signed_event = None


def _active_exporter() -> object:
    """Return the cached exporter, instantiating it from config if necessary."""
    global _cached_exporter  # noqa: PLW0603
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
        from agentobs.exporters.jsonl import SyncJSONLExporter  # noqa: PLC0415
        path = cfg.endpoint or "agentobs_events.jsonl"
        return SyncJSONLExporter(path)

    if name == "console":
        from agentobs.exporters.console import SyncConsoleExporter  # noqa: PLC0415
        return SyncConsoleExporter()

    # Default fallback: use the console exporter.
    from agentobs.exporters.console import SyncConsoleExporter  # noqa: PLC0415
    return SyncConsoleExporter()


# ---------------------------------------------------------------------------
# Event construction helpers
# ---------------------------------------------------------------------------


def _build_event(
    event_type: EventType,
    payload_dict: dict,
    span_id: str | None = None,
    trace_id: str | None = None,
    parent_span_id: str | None = None,
) -> Event:
    """Construct a fully-populated :class:`~agentobs.event.Event` envelope."""
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
        span: A :class:`~agentobs._span.Span` instance.
    """
    # Import here to avoid circular import at module load time.
    from agentobs._span import Span  # noqa: PLC0415

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
    from agentobs._span import AgentStepContext  # noqa: PLC0415

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
    from agentobs._span import AgentRunContext  # noqa: PLC0415

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
    """Export *event* through the active exporter, handling errors per policy.

    Pipeline (in order):
    1. **Redaction** — apply :class:`~agentobs.redact.RedactionPolicy` when
       ``config.redaction_policy`` is set.  PII is masked before anything
       else sees the event.
    2. **Signing** — sign with HMAC-SHA256 and chain to the previous event
       when ``config.signing_key`` is set.
    3. **Export** — hand the event to the active exporter.

    On failure the error is routed through :func:`_handle_export_error` which
    applies the ``on_export_error`` policy (``"warn"`` | ``"raise"`` | ``"drop"``).
    """
    global _prev_signed_event  # noqa: PLW0603
    try:
        cfg = get_config()

        # 1. Redaction (must occur before signing so signatures cover
        #    the already-redacted payload).
        if cfg.redaction_policy is not None:
            event = cfg.redaction_policy.apply(event).event

        # 2. Signing — maintain the audit chain.
        if cfg.signing_key:
            from agentobs.signing import sign  # noqa: PLC0415
            with _sign_lock:
                event = sign(
                    event,
                    org_secret=cfg.signing_key,
                    prev_event=_prev_signed_event,
                )
                _prev_signed_event = event

        # 3. Export.
        exporter = _active_exporter()
        exporter.export(event)  # type: ignore[attr-defined]
    except Exception as exc:
        _handle_export_error(exc)
