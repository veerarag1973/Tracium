"""PII redaction framework for llm-toolkit-schema.

Provides a layered, policy-driven approach to PII identification and redaction
in event payloads.  Redaction is **opt-in per field** — fields must be
explicitly wrapped in :class:`Redactable` to participate in the lifecycle.

Sensitivity ladder
------------------

``low`` < ``medium`` < ``high`` < ``pii`` < ``phi``

A :class:`RedactionPolicy` is configured with a ``min_sensitivity`` level.
Only fields whose sensitivity is **≥ min_sensitivity** are scrubbed when
:meth:`RedactionPolicy.apply` is called.

Usage example
-------------
::

    from tracium.redact import Redactable, RedactionPolicy, Sensitivity, contains_pii
    from tracium import Event, EventType

    policy = RedactionPolicy(
        min_sensitivity=Sensitivity.PII,
        redacted_by="policy:corp-default",
    )

    event = Event(
        event_type=EventType.PROMPT_SAVED,
        source="promptlock@1.0.0",
        payload={
            "version": "v3",
            "author": Redactable("alice@example.com", Sensitivity.PII, {"email"}),
        },
    )

    result = policy.apply(event)
    # result.event.payload["author"]   == "[REDACTED:pii]"
    # result.redaction_count           == 1
    # contains_pii(result.event)       == False

Security guarantees
-------------------
* :class:`Redactable` never exposes its wrapped value in ``__repr__``,
  ``__str__``, or any exception message.
* Exception messages only reveal the *sensitivity level* and *field depth*,
  never the content of the wrapped value.
* The literal replacement strings (``"[REDACTED:pii]"`` etc.) are safe to
  log, export, or include in error messages.
* :meth:`RedactionPolicy.apply` rebuilds the payload recursively so nested
  structures are fully scanned even in deeply-nested payloads.
"""

from __future__ import annotations

import datetime
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Final, FrozenSet, Optional

from tracium.exceptions import LLMSchemaError

if TYPE_CHECKING:
    from tracium.event import Event

__all__ = [
    "Sensitivity",
    "Redactable",
    "RedactionPolicy",
    "RedactionResult",
    "PIINotRedactedError",
    "contains_pii",
    "PII_TYPES",
]

# ---------------------------------------------------------------------------
# Known PII type label constants
# ---------------------------------------------------------------------------

PII_TYPES: Final[frozenset[str]] = frozenset(
    [
        "credit_card",
        "date_of_birth",
        "email",
        "financial_id",
        "ip_address",
        "medical_id",
        "name",
        "phone",
        "ssn",
        "address",
    ]
)

# ---------------------------------------------------------------------------
# Sensitivity ordering
# ---------------------------------------------------------------------------

#: Numeric ordering for each sensitivity level (ascending sensitivity).
_SENSITIVITY_ORDER: Final[dict[str, int]] = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "pii": 3,
    "phi": 4,
}


class Sensitivity(str, Enum):
    """Ordered sensitivity levels for PII classification.

    Levels increase in sensitivity: LOW < MEDIUM < HIGH < PII < PHI.

    * **LOW** — Non-sensitive; informational or operational metadata.
    * **MEDIUM** — Pseudonymous or indirectly identifying data.
    * **HIGH** — Directly identifying but non-regulated (e.g. usernames).
    * **PII** — Directly identifying, regulated personal data (GDPR / CCPA).
    * **PHI** — Protected health information (HIPAA).  Most restrictive.

    Comparison operators (``<``, ``<=``, ``>``, ``>=``) work as expected::

        Sensitivity.PII > Sensitivity.HIGH   # True
        Sensitivity.PHI >= Sensitivity.PII   # True
        Sensitivity.LOW < Sensitivity.MEDIUM # True
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PII = "pii"
    PHI = "phi"

    # ------------------------------------------------------------------
    # Ordered comparisons (delegated to integer order table)
    # ------------------------------------------------------------------

    @property
    def _order(self) -> int:
        """Integer rank — for comparison only; not part of the public API."""
        return _SENSITIVITY_ORDER[self.value]

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Sensitivity):
            return NotImplemented  # type: ignore[return-value]
        return self._order < other._order

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Sensitivity):
            return NotImplemented  # type: ignore[return-value]
        return self._order <= other._order

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Sensitivity):
            return NotImplemented  # type: ignore[return-value]
        return self._order > other._order

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Sensitivity):
            return NotImplemented  # type: ignore[return-value]
        return self._order >= other._order

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str) and not isinstance(other, Sensitivity):
            return str.__eq__(self, other)
        return Enum.__eq__(self, other)

    def __hash__(self) -> int:
        return str.__hash__(self)


# ---------------------------------------------------------------------------
# Redactable wrapper
# ---------------------------------------------------------------------------


class Redactable:
    """Immutable wrapper that marks a payload value as PII-sensitive.

    Wrapping a value in :class:`Redactable` does **not** redact it immediately.
    The value is redacted only when :meth:`RedactionPolicy.apply` is called on
    the event that contains it.

    Security: :class:`Redactable` never surfaces its wrapped value in
    ``__repr__``, ``__str__``, or exceptions.  Only the sensitivity level and
    PII type labels are visible in any string representation.

    Args:
        value:       The raw PII-sensitive value.
        sensitivity: How sensitive the value is.
        pii_types:   Labels describing what type of PII this is.  Use
                     constants from :data:`PII_TYPES` or custom strings.
                     Defaults to an empty frozenset.

    Example::

        field = Redactable("alice@example.com", Sensitivity.PII, {"email"})
        str(field)   # "<Redactable:pii>"   — value hidden
        repr(field)  # "<Redactable sensitivity='pii' pii_types={'email'}>"
    """

    __slots__ = ("_value", "_sensitivity", "_pii_types")

    def __init__(
        self,
        value: Any,
        sensitivity: Sensitivity,
        pii_types: FrozenSet[str] = frozenset(),
    ) -> None:
        object.__setattr__(self, "_value", value)
        object.__setattr__(self, "_sensitivity", sensitivity)
        object.__setattr__(self, "_pii_types", frozenset(pii_types))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def sensitivity(self) -> Sensitivity:
        """The sensitivity level of this field."""
        return self._sensitivity  # type: ignore[return-value]

    @property
    def pii_types(self) -> FrozenSet[str]:
        """Set of PII type labels (e.g. ``{'email', 'pii_identifier'}``)."""
        return self._pii_types  # type: ignore[return-value]

    def reveal(self) -> Any:
        """Return the raw unredacted value.

        Use with extreme care.  Access to raw values should be restricted to
        trusted internal code paths.  Ensure the returned value is never
        logged or included in any observable output.

        Returns:
            The original unwrapped value passed to the constructor.
        """
        return self._value  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Immutability guard
    # ------------------------------------------------------------------

    def __setattr__(self, name: str, value: object) -> None:  # type: ignore[override]
        raise AttributeError("Redactable is immutable — use a new instance to change values")

    # ------------------------------------------------------------------
    # Safe string representations — value intentionally hidden
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"<Redactable sensitivity={self._sensitivity!r} "  # type: ignore[misc]
            f"pii_types={set(self._pii_types)!r}>"  # type: ignore[misc]
        )

    def __str__(self) -> str:
        return f"<Redactable:{self._sensitivity}>"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Redaction result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RedactionResult:
    """Immutable result returned by :meth:`RedactionPolicy.apply`.

    Attributes:
        event:            The newly constructed event with PII removed.
        redaction_count:  How many :class:`Redactable` fields were scrubbed.
        redacted_at:      UTC ISO-8601 timestamp when redaction was applied.
        redacted_by:      The policy identifier string.
    """

    event: "Event"
    redaction_count: int
    redacted_at: str
    redacted_by: str


# ---------------------------------------------------------------------------
# PIINotRedactedError
# ---------------------------------------------------------------------------


class PIINotRedactedError(LLMSchemaError):
    """Raised when :func:`contains_pii` detects un-redacted PII in an event.

    This error signals that a :class:`Redactable` instance is still present in
    the event payload after a :class:`RedactionPolicy` should have been applied.

    Security: the error message never reveals the actual PII value — only field
    path depth and sensitivity information.

    Args:
        count:    Number of unredacted :class:`Redactable` instances found.
        context:  Optional short label for where the check was done.

    Attributes:
        count:   Number of outstanding :class:`Redactable` instances found.
    """

    count: int

    def __init__(self, count: int, context: str = "") -> None:
        self.count = count
        ctx = f" in {context!r}" if context else ""
        super().__init__(
            f"Found {count} unredacted PII field(s){ctx}. "
            "Apply a RedactionPolicy before serialising or exporting this event."
        )


# ---------------------------------------------------------------------------
# RedactionPolicy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RedactionPolicy:
    """Policy that defines which fields to scrub and how to label redactions.

    A policy is immutable; create a new instance to change configuration.
    Apply it to an event via :meth:`apply`, which returns a :class:`RedactionResult`
    containing a new event with PII removed.

    Args:
        min_sensitivity:       Fields with sensitivity **≥** this level are
                               redacted.  Defaults to :attr:`Sensitivity.PII`.
        redacted_by:           Identifier embedded in the redaction metadata
                               (e.g. ``"policy:corp-default"``).
        replacement_template:  String template for the redaction marker.
                               The ``{sensitivity}`` placeholder is replaced
                               with the field's sensitivity level value.
                               Defaults to ``"[REDACTED:{sensitivity}]"``.

    Example::

        policy = RedactionPolicy(
            min_sensitivity=Sensitivity.HIGH,
            redacted_by="policy:strict",
        )
        result = policy.apply(event)
    """

    min_sensitivity: Sensitivity = Sensitivity.PII
    redacted_by: str = "policy:default"
    replacement_template: str = "[REDACTED:{sensitivity}]"

    def _make_marker(self, sensitivity: Sensitivity) -> str:
        """Format the replacement string for a given sensitivity level."""
        return self.replacement_template.format(sensitivity=sensitivity.value)

    def _should_redact(self, r: Redactable) -> bool:
        """Return True if the Redactable field meets the policy threshold."""
        return r.sensitivity >= self.min_sensitivity

    def _redact_value(self, value: Any, counter: list[int]) -> Any:
        """Recursively replace Redactable instances in *value*.

        Args:
            value:   Any Python value (dict, list, Redactable, or scalar).
            counter: Single-element list used as a mutable integer counter.

        Returns:
            The value with any qualifying Redactable instances replaced by
            their marker strings.  Non-Redactable values are returned as-is.
        """
        if isinstance(value, Redactable):
            if self._should_redact(value):
                counter[0] += 1
                return self._make_marker(value.sensitivity)
            # Below threshold — leave as-is for now;
            # contains_pii() will detect it post-apply if needed.
            return value
        if isinstance(value, dict):
            return {k: self._redact_value(v, counter) for k, v in value.items()}
        if isinstance(value, list):
            return [self._redact_value(v, counter) for v in value]
        if isinstance(value, tuple):
            return tuple(self._redact_value(v, counter) for v in value)
        return value

    def apply(self, event: "Event") -> RedactionResult:
        """Apply this policy to *event*, returning a new redacted event.

        All :class:`Redactable` fields in the payload whose sensitivity is ≥
        :attr:`min_sensitivity` are replaced with safe marker strings.
        Redaction metadata is appended under the reserved ``__redacted_*``
        keys in the payload.

        The original event is **not** mutated; a new :class:`Event` is returned
        inside the :class:`RedactionResult`.

        Args:
            event: The event whose payload should be scanned and redacted.

        Returns:
            A :class:`RedactionResult` with the new event and redaction stats.

        Raises:
            LLMSchemaError: If reconstruction of the redacted event fails for
                structural reasons.
        """
        # Import here to avoid circular dependency at module load time.
        from tracium.event import Event  # noqa: PLC0415

        counter: list[int] = [0]
        redacted_payload = self._redact_value(dict(event.payload), counter)

        now = _utcnow_iso()

        if isinstance(redacted_payload, dict) and counter[0] > 0:
            redacted_payload["__redacted_at"] = now
            redacted_payload["__redacted_by"] = self.redacted_by
            redacted_payload["__redaction_count"] = counter[0]

        new_event = Event(
            schema_version=event.schema_version,
            event_id=event.event_id,
            event_type=event.event_type,
            timestamp=event.timestamp,
            source=event.source,
            payload=redacted_payload,
            trace_id=event.trace_id,
            span_id=event.span_id,
            parent_span_id=event.parent_span_id,
            org_id=event.org_id,
            team_id=event.team_id,
            actor_id=event.actor_id,
            session_id=event.session_id,
            tags=event.tags,
            checksum=event.checksum,
            signature=event.signature,
            prev_id=event.prev_id,
        )

        return RedactionResult(
            event=new_event,
            redaction_count=counter[0],
            redacted_at=now,
            redacted_by=self.redacted_by,
        )


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def contains_pii(event: "Event") -> bool:
    """Return ``True`` if any unredacted :class:`Redactable` values remain.

    Use this after :meth:`RedactionPolicy.apply` to verify that all qualifying
    fields were scrubbed before the event is serialised or exported.

    Does **not** raise; callers decide the appropriate response.  For a
    strict raising version, see :func:`assert_redacted`.

    Args:
        event: The event to inspect.

    Returns:
        ``True`` if at least one :class:`Redactable` instance is found in the
        payload (at any nesting depth).  ``False`` if the payload is clean.

    Example::

        if contains_pii(event):
            raise RuntimeError("Unredacted PII detected — cannot export")
    """
    return _has_redactable(event.payload)


def assert_redacted(event: "Event", context: str = "") -> None:
    """Assert that *event* contains no unredacted :class:`Redactable` values.

    This is the strict variant of :func:`contains_pii`.  It raises
    :exc:`PIINotRedactedError` if any :class:`Redactable` instances remain.

    Args:
        event:   The event to inspect.
        context: Optional short label for the error message (e.g. filename).

    Raises:
        PIINotRedactedError: If any :class:`Redactable` instances are found.

    Example::

        assert_redacted(event, context="export_to_otlp")
    """
    count = _count_redactable(event.payload)
    if count > 0:
        raise PIINotRedactedError(count=count, context=context)


# ---------------------------------------------------------------------------
# Internal helpers (module-private)
# ---------------------------------------------------------------------------


def _has_redactable(value: Any) -> bool:
    """Return True if *value* contains any Redactable instance (recursive)."""
    if isinstance(value, Redactable):
        return True
    if isinstance(value, Mapping):
        return any(_has_redactable(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_has_redactable(v) for v in value)
    return False


def _count_redactable(value: Any, _depth: int = 0) -> int:
    """Count the total number of Redactable instances in *value* (recursive)."""
    if isinstance(value, Redactable):
        return 1
    if isinstance(value, Mapping):
        return sum(_count_redactable(v, _depth + 1) for v in value.values())
    if isinstance(value, (list, tuple)):
        return sum(_count_redactable(v, _depth + 1) for v in value)
    return 0


def _utcnow_iso() -> str:
    """Return current UTC time as an ISO-8601 string (same format as Event)."""
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond:06d}Z"
