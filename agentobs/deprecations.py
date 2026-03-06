"""Deprecation registry for agentobs event types.

Tracks which event types are deprecated, their deprecation date, planned
sunset date, and recommended replacement.  Used by governance policies,
the CLI, and integrations to warn operators before sunset.

Example::

    from agentobs.deprecations import (
        mark_deprecated,
        get_deprecation_notice,
        warn_if_deprecated,
    )

    mark_deprecated(
        "llm.trace.span.started",
        since="1.0",
        sunset="2.0",
        replacement="llm.trace.span.span_started",
    )

    notice = get_deprecation_notice("llm.trace.span.started")
    # DeprecationNotice(event_type='llm.trace.span.started', since='1.0', ...)

    warn_if_deprecated("llm.trace.span.started")   # emits DeprecationWarning
"""

from __future__ import annotations

import threading
import warnings
from dataclasses import dataclass

__all__ = [
    "DeprecationNotice",
    "DeprecationRegistry",
    "get_deprecation_notice",
    "get_registry",
    "list_deprecated",
    "mark_deprecated",
    "warn_if_deprecated",
]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeprecationNotice:
    """Record of a deprecated event type.

    Attributes:
        event_type:   The event type string that is deprecated.
        since:        Schema version when the deprecation was introduced
                      (e.g. ``"1.0"``).
        sunset:       Schema version at which the type will be removed
                      (e.g. ``"2.0"``).
        replacement:  Recommended replacement event type, or ``None`` if there
                      is no direct replacement.
        notes:        Optional freeform notes for human readers.
    """

    event_type: str
    since: str
    sunset: str
    replacement: str | None = None
    notes: str | None = None

    def format_message(self) -> str:
        """Return a human-readable deprecation message.

        Returns:
            Formatted deprecation warning string.
        """
        msg = (
            f"Event type {self.event_type!r} is deprecated since v{self.since} "
            f"and will be removed in v{self.sunset}."
        )
        if self.replacement:
            msg += f" Use {self.replacement!r} instead."
        if self.notes:
            msg += f" Note: {self.notes}"
        return msg

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"DeprecationNotice(event_type={self.event_type!r}, "
            f"since={self.since!r}, sunset={self.sunset!r})"
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class DeprecationRegistry:
    """Thread-safe registry of deprecated event types.

    Maintains a mapping of event type → :class:`DeprecationNotice`.  All
    public methods are thread-safe.

    Example::

        registry = DeprecationRegistry()
        registry.mark_deprecated(
            "llm.legacy.type",
            since="1.0",
            sunset="2.0",
            replacement="llm.new.type",
        )
        notice = registry.get("llm.legacy.type")
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._notices: dict[str, DeprecationNotice] = {}

    def mark_deprecated(
        self,
        event_type: str,
        *,
        since: str,
        sunset: str,
        replacement: str | None = None,
        notes: str | None = None,
    ) -> DeprecationNotice:
        """Register *event_type* as deprecated.

        If *event_type* is already registered, the record is **updated** with
        the new values.

        Args:
            event_type:   The event type string to deprecate.
            since:        Version when the deprecation was introduced.
            sunset:       Version when the type will be removed.
            replacement:  Optional recommended replacement event type.
            notes:        Optional freeform notes.

        Returns:
            The created or updated :class:`DeprecationNotice`.

        Raises:
            ValueError: If *event_type*, *since*, or *sunset* are empty.
        """
        if not event_type or not event_type.strip():
            raise ValueError("event_type must be a non-empty string")
        if not since:
            raise ValueError("since must be a non-empty string")
        if not sunset:
            raise ValueError("sunset must be a non-empty string")

        notice = DeprecationNotice(
            event_type=event_type.strip(),
            since=since,
            sunset=sunset,
            replacement=replacement,
            notes=notes,
        )
        with self._lock:
            self._notices[event_type.strip()] = notice
        return notice

    def get(self, event_type: str) -> DeprecationNotice | None:
        """Return the :class:`DeprecationNotice` for *event_type*, or ``None``.

        Args:
            event_type: The event type to look up.

        Returns:
            :class:`DeprecationNotice` or ``None`` if not deprecated.
        """
        with self._lock:
            return self._notices.get(event_type)

    def is_deprecated(self, event_type: str) -> bool:
        """Return ``True`` if *event_type* is registered as deprecated.

        Args:
            event_type: The event type to check.

        Returns:
            ``True`` if deprecated, ``False`` otherwise.
        """
        with self._lock:
            return event_type in self._notices

    def warn_if_deprecated(self, event_type: str) -> None:
        """Issue a :class:`DeprecationWarning` if *event_type* is deprecated.

        A no-op when the type is not registered as deprecated.

        Args:
            event_type: The event type to check and potentially warn about.
        """
        notice = self.get(event_type)
        if notice is not None:
            warnings.warn(notice.format_message(), DeprecationWarning, stacklevel=3)

    def list_all(self) -> list[DeprecationNotice]:
        """Return a snapshot of all registered deprecation notices.

        Returns:
            List of all :class:`DeprecationNotice` instances, sorted by
            event type for deterministic output.
        """
        with self._lock:
            return sorted(self._notices.values(), key=lambda n: n.event_type)

    def remove(self, event_type: str) -> bool:
        """Remove the deprecation notice for *event_type* (for testing).

        Args:
            event_type: The event type to un-deprecate.

        Returns:
            ``True`` if a notice was removed, ``False`` if not found.
        """
        with self._lock:
            return self._notices.pop(event_type, None) is not None

    def clear(self) -> None:
        """Remove all deprecation notices (useful in tests)."""
        with self._lock:
            self._notices.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._notices)

    def __repr__(self) -> str:  # pragma: no cover
        return f"DeprecationRegistry(notices={len(self)})"


# ---------------------------------------------------------------------------
# Module-level singleton and helpers
# ---------------------------------------------------------------------------

_GLOBAL_REGISTRY = DeprecationRegistry()


def get_registry() -> DeprecationRegistry:
    """Return the module-level :class:`DeprecationRegistry` singleton.

    Returns:
        The global :class:`DeprecationRegistry` instance.
    """
    return _GLOBAL_REGISTRY


def mark_deprecated(
    event_type: str,
    *,
    since: str,
    sunset: str,
    replacement: str | None = None,
    notes: str | None = None,
) -> DeprecationNotice:
    """Register *event_type* as deprecated in the global registry.

    Convenience wrapper around :meth:`DeprecationRegistry.mark_deprecated`.

    Args:
        event_type:   The event type string to deprecate.
        since:        Version when the deprecation was introduced.
        sunset:       Version when the type will be removed.
        replacement:  Optional recommended replacement event type.
        notes:        Optional freeform notes.

    Returns:
        The created :class:`DeprecationNotice`.

    Raises:
        ValueError: See :meth:`DeprecationRegistry.mark_deprecated`.
    """
    return _GLOBAL_REGISTRY.mark_deprecated(
        event_type,
        since=since,
        sunset=sunset,
        replacement=replacement,
        notes=notes,
    )


def get_deprecation_notice(event_type: str) -> DeprecationNotice | None:
    """Return the deprecation notice for *event_type* from the global registry.

    Args:
        event_type: The event type to look up.

    Returns:
        :class:`DeprecationNotice` or ``None`` if not deprecated.
    """
    return _GLOBAL_REGISTRY.get(event_type)


def warn_if_deprecated(event_type: str) -> None:
    """Issue a :class:`DeprecationWarning` if *event_type* is globally deprecated.

    Args:
        event_type: The event type to check.
    """
    _GLOBAL_REGISTRY.warn_if_deprecated(event_type)


def list_deprecated() -> list[DeprecationNotice]:
    """Return all globally registered deprecation notices, sorted by event type.

    Returns:
        List of all :class:`DeprecationNotice` instances.
    """
    return _GLOBAL_REGISTRY.list_all()
