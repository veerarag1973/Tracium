"""llm_toolkit_schema.namespaces.audit — Audit chain payload types (RFC-0001 §11).

Classes
-------
AuditKeyRotatedPayload      llm.audit.key.rotated
AuditChainVerifiedPayload   llm.audit.chain.verified
AuditChainTamperedPayload   llm.audit.chain.tampered
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = [
    "AuditKeyRotatedPayload",
    "AuditChainVerifiedPayload",
    "AuditChainTamperedPayload",
]

_VALID_ROTATION_REASONS = frozenset({
    "scheduled", "suspected_compromise", "policy_update", "key_expiry", "manual"
})
_VALID_SEVERITIES = frozenset({"low", "medium", "high", "critical"})


@dataclass
class AuditKeyRotatedPayload:
    """RFC-0001 §11.5 — An HMAC signing key was rotated.

    ``key_algorithm`` defaults to ``"HMAC-SHA256"`` (the only algorithm
    mandated by the RFC).  ``effective_from_event_id`` is the ULID of the
    first event signed with the new key.
    """

    key_id: str
    previous_key_id: str
    rotated_at: str   # ISO 8601 timestamp with exactly 6 decimal places
    rotated_by: str
    rotation_reason: Optional[str] = None
    key_algorithm: str = "HMAC-SHA256"
    effective_from_event_id: Optional[str] = None  # ULID

    def __post_init__(self) -> None:
        if not self.key_id:
            raise ValueError("AuditKeyRotatedPayload.key_id must be non-empty")
        if not self.previous_key_id:
            raise ValueError("AuditKeyRotatedPayload.previous_key_id must be non-empty")
        if not self.rotated_at:
            raise ValueError("AuditKeyRotatedPayload.rotated_at must be non-empty")
        if not self.rotated_by:
            raise ValueError("AuditKeyRotatedPayload.rotated_by must be non-empty")
        if self.rotation_reason is not None and self.rotation_reason not in _VALID_ROTATION_REASONS:
            raise ValueError(
                f"AuditKeyRotatedPayload.rotation_reason must be one of {sorted(_VALID_ROTATION_REASONS)}"
            )

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "key_id": self.key_id,
            "previous_key_id": self.previous_key_id,
            "rotated_at": self.rotated_at,
            "rotated_by": self.rotated_by,
            "key_algorithm": self.key_algorithm,
        }
        if self.rotation_reason is not None:
            d["rotation_reason"] = self.rotation_reason
        if self.effective_from_event_id is not None:
            d["effective_from_event_id"] = self.effective_from_event_id
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditKeyRotatedPayload":
        return cls(
            key_id=data["key_id"],
            previous_key_id=data["previous_key_id"],
            rotated_at=data["rotated_at"],
            rotated_by=data["rotated_by"],
            rotation_reason=data.get("rotation_reason"),
            key_algorithm=data.get("key_algorithm", "HMAC-SHA256"),
            effective_from_event_id=data.get("effective_from_event_id"),
        )


@dataclass
class AuditChainVerifiedPayload:
    """RFC-0001 §11 — An audit chain segment was verified intact."""

    verified_from_event_id: str
    verified_to_event_id: str
    event_count: int
    verified_at: str
    verified_by: str

    def __post_init__(self) -> None:
        if not self.verified_from_event_id:
            raise ValueError("AuditChainVerifiedPayload.verified_from_event_id must be non-empty")
        if not self.verified_to_event_id:
            raise ValueError("AuditChainVerifiedPayload.verified_to_event_id must be non-empty")
        if not isinstance(self.event_count, int) or self.event_count < 0:
            raise ValueError("AuditChainVerifiedPayload.event_count must be a non-negative int")
        if not self.verified_at:
            raise ValueError("AuditChainVerifiedPayload.verified_at must be non-empty")
        if not self.verified_by:
            raise ValueError("AuditChainVerifiedPayload.verified_by must be non-empty")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verified_from_event_id": self.verified_from_event_id,
            "verified_to_event_id": self.verified_to_event_id,
            "event_count": self.event_count,
            "verified_at": self.verified_at,
            "verified_by": self.verified_by,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditChainVerifiedPayload":
        return cls(
            verified_from_event_id=data["verified_from_event_id"],
            verified_to_event_id=data["verified_to_event_id"],
            event_count=int(data["event_count"]),
            verified_at=data["verified_at"],
            verified_by=data["verified_by"],
        )


@dataclass
class AuditChainTamperedPayload:
    """RFC-0001 §11 — Tampering or a gap was detected in the audit chain."""

    first_tampered_event_id: str
    tampered_count: int
    detected_at: str
    detected_by: str
    gap_count: Optional[int] = None
    gap_prev_ids: List[str] = field(default_factory=list)
    severity: Optional[str] = None  # "low"|"medium"|"high"|"critical"

    def __post_init__(self) -> None:
        if not self.first_tampered_event_id:
            raise ValueError("AuditChainTamperedPayload.first_tampered_event_id must be non-empty")
        if not isinstance(self.tampered_count, int) or self.tampered_count < 0:
            raise ValueError("AuditChainTamperedPayload.tampered_count must be a non-negative int")
        if not self.detected_at:
            raise ValueError("AuditChainTamperedPayload.detected_at must be non-empty")
        if not self.detected_by:
            raise ValueError("AuditChainTamperedPayload.detected_by must be non-empty")
        if self.severity is not None and self.severity not in _VALID_SEVERITIES:
            raise ValueError(f"AuditChainTamperedPayload.severity must be one of {sorted(_VALID_SEVERITIES)}")

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "first_tampered_event_id": self.first_tampered_event_id,
            "tampered_count": self.tampered_count,
            "detected_at": self.detected_at,
            "detected_by": self.detected_by,
        }
        if self.gap_count is not None:
            d["gap_count"] = self.gap_count
        if self.gap_prev_ids:
            d["gap_prev_ids"] = list(self.gap_prev_ids)
        if self.severity is not None:
            d["severity"] = self.severity
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditChainTamperedPayload":
        return cls(
            first_tampered_event_id=data["first_tampered_event_id"],
            tampered_count=int(data["tampered_count"]),
            detected_at=data["detected_at"],
            detected_by=data["detected_by"],
            gap_count=int(data["gap_count"]) if "gap_count" in data else None,
            gap_prev_ids=list(data.get("gap_prev_ids", [])),
            severity=data.get("severity"),
        )