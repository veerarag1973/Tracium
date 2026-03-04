"""Schema governance policies for traciumema events.

Provides a policy engine that can:

* **Block** specific event types from being created or exported (e.g. legacy
  or disallowed event types).
* **Warn** when deprecated event types are used, without hard-blocking.
* Allow **custom rule callbacks** for fine-grained governance checks.

Typical usage::

    from tracium.governance import EventGovernancePolicy, GovernanceViolationError

    policy = EventGovernancePolicy(
        blocked_types={"LEGACY_TRACE"},
        warn_deprecated={"OLD_EVAL"},
    )

    # Hard block — raises GovernanceViolationError
    policy.check_event(event)   # raises if event.event_type in blocked_types

    # Module-level policy (applied globally)
    from tracium.governance import set_global_policy, check_event

    set_global_policy(policy)
    check_event(event)          # uses global policy
"""

from __future__ import annotations

import threading
import warnings
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from tracium.event import Event

__all__ = [
    "EventGovernancePolicy",
    "GovernanceViolationError",
    "GovernanceWarning",
    "check_event",
    "get_global_policy",
    "set_global_policy",
]


# ---------------------------------------------------------------------------
# Exceptions / warnings
# ---------------------------------------------------------------------------


class GovernanceViolationError(Exception):
    """Raised when an event violates a governance policy.

    Attributes:
        event_type:  The event type that triggered the violation.
        reason:      Human-readable explanation.
    """

    def __init__(self, event_type: str, reason: str) -> None:
        self.event_type = event_type
        self.reason = reason
        super().__init__(f"Governance violation for event type {event_type!r}: {reason}")


class GovernanceWarning(UserWarning):
    """Warning issued when a deprecated-but-not-blocked event type is used."""


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


@dataclass
class EventGovernancePolicy:
    """Policy that enforces event-level schema governance rules.

    Three tiers of enforcement are supported:

    1. **Blocked types** — hard error, :exc:`GovernanceViolationError` raised.
    2. **Deprecated types** — soft warning via Python :mod:`warnings`.
    3. **Custom rules** — callables that receive the :class:`~tracium.event.Event`
       and return ``None`` (allow) or a ``str`` reason (block).

    Attributes:
        blocked_types:      Event type strings that are completely disallowed.
        warn_deprecated:    Event type strings that are deprecated and trigger a
                            :class:`GovernanceWarning` (but not an error).
        custom_rules:       List of callables ``(event) -> Optional[str]``.
                            If a callable returns a non-empty string, the event
                            is blocked with that string as the reason.
        strict_unknown:     When ``True``, event types absent from the
                            schema registry are **blocked** and raise
                            :exc:`GovernanceViolationError` (default ``False``
                            keeps the original allow-all behaviour).

    Example::

        policy = EventGovernancePolicy(
            blocked_types={"LEGACY_TRACE", "DEPRECATED_TOOL_CALL"},
            warn_deprecated={"OLD_EVAL_SCORE"},
        )
        policy.check_event(event)   # raises or warns as appropriate
    """

    blocked_types: set[str] = field(default_factory=set)
    warn_deprecated: set[str] = field(default_factory=set)
    custom_rules: list[Callable[[Event], str | None]] = field(default_factory=list)
    strict_unknown: bool = False

    def check_event(self, event: Event) -> None:
        """Check *event* against this policy.

        Args:
            event: The event to check.

        Raises:
            GovernanceViolationError: If the event type is blocked or any
                                      custom rule returns a reason.

        Warns:
            GovernanceWarning: If the event type is deprecated.
        """
        et = str(event.event_type)

        # 1. Hard block.
        if et in self.blocked_types:
            raise GovernanceViolationError(
                et, f"Event type {et!r} is blocked by governance policy."
            )

        # 2. Deprecation warning.
        if et in self.warn_deprecated:
            warnings.warn(
                f"Event type {et!r} is deprecated. "
                "Update your code to use the recommended replacement.",
                GovernanceWarning,
                stacklevel=4,
            )

        # 3. Custom rules.
        for rule in self.custom_rules:
            reason = rule(event)
            if reason:
                raise GovernanceViolationError(et, reason)

        # 4. Strict unknown — block event types absent from the schema registry.
        if self.strict_unknown:
            from tracium.types import is_registered  # noqa: PLC0415
            if not is_registered(et):
                raise GovernanceViolationError(
                    et,
                    f"Event type {et!r} is not registered in the schema registry "
                    "(strict_unknown=True).",
                )

    def add_blocked_type(self, event_type: str) -> None:
        """Add *event_type* to the blocked set at runtime.

        Args:
            event_type: The event type string to block.
        """
        if not event_type:
            raise ValueError("event_type must be a non-empty string")
        self.blocked_types.add(event_type)

    def add_deprecated_type(self, event_type: str) -> None:
        """Mark *event_type* as deprecated (warning-only) at runtime.

        Args:
            event_type: The event type string to deprecate.
        """
        if not event_type:
            raise ValueError("event_type must be a non-empty string")
        self.warn_deprecated.add(event_type)

    def add_rule(self, rule: Callable[[Event], str | None]) -> None:
        """Append a custom governance rule callable.

        Args:
            rule: A callable that accepts an :class:`~tracium.event.Event`
                  and returns ``None`` to allow or a non-empty string reason to block.

        Raises:
            TypeError: If *rule* is not callable.
        """
        if not callable(rule):
            raise TypeError("rule must be callable")
        self.custom_rules.append(rule)

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    def blocked(self) -> frozenset[str]:
        """Return an immutable snapshot of blocked event types.

        Returns:
            Frozen set of blocked event type strings.
        """
        return frozenset(self.blocked_types)

    def deprecated(self) -> frozenset[str]:
        """Return an immutable snapshot of deprecated event types.

        Returns:
            Frozen set of deprecated event type strings.
        """
        return frozenset(self.warn_deprecated)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"EventGovernancePolicy("
            f"blocked={sorted(self.blocked_types)!r}, "
            f"deprecated={sorted(self.warn_deprecated)!r}, "
            f"rules={len(self.custom_rules)})"
        )


# ---------------------------------------------------------------------------
# Global policy singleton
# ---------------------------------------------------------------------------

_GLOBAL_LOCK = threading.Lock()
_GLOBAL_POLICY: EventGovernancePolicy | None = None


def get_global_policy() -> EventGovernancePolicy | None:
    """Return the currently installed global governance policy, or ``None``.

    Returns:
        The active :class:`EventGovernancePolicy` or ``None`` if none has been
        set.
    """
    with _GLOBAL_LOCK:
        return _GLOBAL_POLICY


def set_global_policy(policy: EventGovernancePolicy | None) -> None:
    """Install *policy* as the global governance policy.

    Pass ``None`` to disable global governance enforcement.

    Args:
        policy: The :class:`EventGovernancePolicy` to activate, or ``None``
                to clear the global policy.

    Raises:
        TypeError: If *policy* is neither an :class:`EventGovernancePolicy`
                   nor ``None``.

    Example::

        set_global_policy(
            EventGovernancePolicy(blocked_types={"LEGACY_TRACE"})
        )
    """
    if policy is not None and not isinstance(policy, EventGovernancePolicy):
        raise TypeError(
            f"policy must be an EventGovernancePolicy or None, got {type(policy).__name__!r}"
        )
    with _GLOBAL_LOCK:
        global _GLOBAL_POLICY  # noqa: PLW0603
        _GLOBAL_POLICY = policy


def check_event(event: Event) -> None:
    """Check *event* against the global governance policy.

    A no-op if no global policy has been set.

    Args:
        event: The event to check.

    Raises:
        GovernanceViolationError: If the event is blocked by the global policy.

    Warns:
        GovernanceWarning: If the event type is deprecated.
    """
    with _GLOBAL_LOCK:
        policy = _GLOBAL_POLICY
    if policy is not None:
        policy.check_event(event)
