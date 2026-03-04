"""Performance benchmark tests validating all NFR targets.

NFR targets (from implementationplan.md):
    - Event creation (no signing)          < 1ms   per event
    - Event creation + HMAC signing        < 5ms   per event
    - JSON serialisation of 1,000 events   < 50ms  total
    - OTLP attribute serialisation (500)   < 200ms total

Each test is marked ``@pytest.mark.perf`` so it can be run selectively::

    pytest -m perf -v
"""

from __future__ import annotations

import time

import pytest

from llm_toolkit_schema import Event, EventType
from llm_toolkit_schema.export.otlp import _event_to_attributes
from llm_toolkit_schema.signing import sign

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_SOURCE = "benchmark-tool@1.0.0"
_SECRET = "benchmark-signing-secret"
_PAYLOAD = {"span_name": "llm.chat", "status": "ok", "tokens": 128}


def _make_event() -> Event:
    return Event(
        event_type=EventType.TRACE_SPAN_COMPLETED,
        source=_SOURCE,
        payload=_PAYLOAD,
    )


# ---------------------------------------------------------------------------
# NFR: Event creation (no signing) — < 1ms each → 1 000 events < 1 000ms
# ---------------------------------------------------------------------------


@pytest.mark.perf
def test_nfr_event_creation_no_signing() -> None:
    """1 000 plain Event instances must be created in under 1 000ms (< 1ms each)."""
    n = 1_000
    deadline_seconds = 1.0

    start = time.perf_counter()
    for _ in range(n):
        Event(
            event_type=EventType.TRACE_SPAN_COMPLETED,
            source=_SOURCE,
            payload=_PAYLOAD,
        )
    elapsed = time.perf_counter() - start

    assert elapsed < deadline_seconds, (
        f"Event creation too slow: {n} events in {elapsed * 1000:.1f}ms "
        f"(limit {deadline_seconds * 1000:.0f}ms)"
    )


# ---------------------------------------------------------------------------
# NFR: Event creation + HMAC signing — < 5ms each → 100 events < 500ms
# ---------------------------------------------------------------------------


@pytest.mark.perf
def test_nfr_event_creation_and_signing() -> None:
    """100 signed Event instances must be produced in under 500ms (< 5ms each)."""
    n = 100
    deadline_seconds = 0.5

    base = _make_event()
    start = time.perf_counter()
    prev = None
    for _ in range(n):
        evt = _make_event()
        signed = sign(evt, _SECRET, prev_event=prev)
        prev = signed
    elapsed = time.perf_counter() - start

    assert elapsed < deadline_seconds, (
        f"Signing too slow: {n} events in {elapsed * 1000:.1f}ms "
        f"(limit {deadline_seconds * 1000:.0f}ms)"
    )


# ---------------------------------------------------------------------------
# NFR: JSON serialisation of 1 000 events — < 50ms total
# ---------------------------------------------------------------------------


@pytest.mark.perf
def test_nfr_json_serialisation_1000_events() -> None:
    """1 000 Event.to_json() calls must complete in under 50ms."""
    events = [_make_event() for _ in range(1_000)]
    deadline_seconds = 0.050

    start = time.perf_counter()
    for evt in events:
        evt.to_json()
    elapsed = time.perf_counter() - start

    assert elapsed < deadline_seconds, (
        f"JSON serialisation too slow: 1 000 events in {elapsed * 1000:.1f}ms "
        f"(limit {deadline_seconds * 1000:.0f}ms)"
    )


# ---------------------------------------------------------------------------
# NFR: OTLP attribute serialisation of 500 events — < 200ms total
# (pure _event_to_attributes computation, no HTTP round-trip)
# ---------------------------------------------------------------------------


@pytest.mark.perf
def test_nfr_otlp_serialisation_500_events() -> None:
    """500 _event_to_attributes() calls must complete in under 200ms."""
    events = [_make_event() for _ in range(500)]
    deadline_seconds = 0.200

    start = time.perf_counter()
    for evt in events:
        _event_to_attributes(evt)
    elapsed = time.perf_counter() - start

    assert elapsed < deadline_seconds, (
        f"OTLP attribute serialisation too slow: 500 events in {elapsed * 1000:.1f}ms "
        f"(limit {deadline_seconds * 1000:.0f}ms)"
    )
