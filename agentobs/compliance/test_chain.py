"""agentobs.compliance.test_chain — HMAC audit-chain integrity verification.

Provides a high-level API over :mod:`agentobs.signing` to check that an ordered
sequence of signed events forms a cryptographically valid and gap-free audit
chain.

Public API
----------
- :class:`ChainIntegrityViolation` — a single chain failure record.
- :class:`ChainIntegrityResult`    — aggregated result for a batch.
- :func:`verify_chain_integrity`   — main entry point.
- :func:`_check_monotonic_timestamps` — internal helper (exposed for testing).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "ChainIntegrityResult",
    "ChainIntegrityViolation",
    "verify_chain_integrity",
]


@dataclass
class ChainIntegrityViolation:
    """A single chain integrity violation.

    Attributes:
        violation_type: One of ``"tampered"``, ``"gap"``, or
                        ``"non_monotonic_timestamp"``.
        event_id:       ID of the offending event, or ``None`` for structural
                        violations that cannot be attributed to a single event.
        detail:         Human-readable description of the violation.
    """

    violation_type: str
    event_id: str | None
    detail: str


@dataclass
class ChainIntegrityResult:
    """Aggregated result from :func:`verify_chain_integrity`.

    Attributes:
        passed:          ``True`` only when *violations* is empty.
        chain_result:    The low-level :class:`~agentobs.signing.ChainVerificationResult`,
                         or ``None`` when the input was empty.
        violations:      All detected failures.
        events_verified: Number of events that were checked.
        gaps_detected:   Number of ``prev_id`` linkage gaps detected.
    """

    passed: bool
    chain_result: object  # ChainVerificationResult | None
    violations: list[ChainIntegrityViolation] = field(default_factory=list)
    events_verified: int = 0
    gaps_detected: int = 0

    def __bool__(self) -> bool:
        return self.passed


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_monotonic_timestamps(
    events: Sequence[object],  # Sequence[Event]
) -> list[ChainIntegrityViolation]:
    """Return violations for any event whose timestamp precedes its predecessor.

    Args:
        events: Ordered sequence of :class:`~agentobs.event.Event` objects.

    Returns:
        List of :class:`ChainIntegrityViolation` with
        ``violation_type="non_monotonic_timestamp"``.
    """
    from agentobs.event import _parse_timestamp  # noqa: PLC0415

    violations: list[ChainIntegrityViolation] = []
    prev_dt = None

    for evt in events:
        ts = getattr(evt, "timestamp", None)
        eid = getattr(evt, "event_id", None)
        if ts is None:
            continue
        try:
            dt = _parse_timestamp(ts)
        except (ValueError, TypeError):
            continue  # unparseable timestamp — already covered by CHK-1

        if prev_dt is not None and dt < prev_dt:
            violations.append(
                ChainIntegrityViolation(
                    violation_type="non_monotonic_timestamp",
                    event_id=eid,
                    detail=(
                        f"timestamp {ts!r} precedes predecessor "
                        f"({prev_dt.isoformat()})"
                    ),
                )
            )
        else:
            prev_dt = dt  # only advance the cursor on non-violation events

    return violations


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def verify_chain_integrity(
    events: Sequence[object],  # Sequence[Event]
    org_secret: str,
    *,
    check_monotonic_timestamps: bool = True,
) -> ChainIntegrityResult:
    """Verify the HMAC audit chain for *events*.

    Performs three independent checks:

    1. **Per-event signature** — each event's ``checksum`` and ``signature``
       are recomputed and compared (``violation_type="tampered"``).
    2. **Chain linkage** — each event's ``prev_id`` must equal the
       ``event_id`` of its predecessor (``violation_type="gap"``).
    3. **Timestamp monotonicity** — timestamps must be non-decreasing
       (``violation_type="non_monotonic_timestamp"``).  Disabled when
       ``check_monotonic_timestamps=False``.

    Args:
        events:                    Ordered sequence of signed events.
        org_secret:                HMAC key used when the chain was signed.
        check_monotonic_timestamps: When ``True`` (default) also check that
                                    timestamps are ascending.

    Returns:
        :class:`ChainIntegrityResult` with full violation details.

    Example::

        result = verify_chain_integrity(signed_events, org_secret="my-key")
        if not result:
            for v in result.violations:
                print(v.violation_type, v.event_id)
    """
    from agentobs.signing import verify, verify_chain  # noqa: PLC0415

    event_list = list(events)

    if not event_list:
        return ChainIntegrityResult(
            passed=True,
            chain_result=None,
            violations=[],
            events_verified=0,
            gaps_detected=0,
        )

    violations: list[ChainIntegrityViolation] = []

    # ------------------------------------------------------------------
    # 1. Run the low-level chain verifier for linkage + global summary.
    # ------------------------------------------------------------------
    chain_result = verify_chain(event_list, org_secret)
    gap_set = frozenset(chain_result.gaps)

    # ------------------------------------------------------------------
    # 2. Per-event signature check (tampered detection).
    # ------------------------------------------------------------------
    for evt in event_list:
        eid = getattr(evt, "event_id", None)
        if not verify(evt, org_secret):  # type: ignore[arg-type]
            violations.append(
                ChainIntegrityViolation(
                    violation_type="tampered",
                    event_id=eid,
                    detail=f"Signature verification failed for event {eid!r}",
                )
            )

    # ------------------------------------------------------------------
    # 3. Gap violations.
    # ------------------------------------------------------------------
    for evt in event_list:
        eid = getattr(evt, "event_id", None)
        if eid in gap_set:
            violations.append(
                ChainIntegrityViolation(
                    violation_type="gap",
                    event_id=eid,
                    detail=f"prev_id linkage broken at event {eid!r}",
                )
            )

    # ------------------------------------------------------------------
    # 4. Optional monotonic timestamp check.
    # ------------------------------------------------------------------
    if check_monotonic_timestamps:
        violations.extend(_check_monotonic_timestamps(event_list))

    passed = len(violations) == 0

    return ChainIntegrityResult(
        passed=passed,
        chain_result=chain_result,
        violations=violations,
        events_verified=len(event_list),
        gaps_detected=len(chain_result.gaps),
    )
