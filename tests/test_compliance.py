"""Tests for the tracium.compliance package.

Covers:
- compliance.test_isolation  (IsolationViolation, IsolationResult,
                               verify_tenant_isolation, verify_events_scoped,
                               _check_org_consistency, _check_org_disjoint)
- compliance.test_chain      (ChainIntegrityViolation, ChainIntegrityResult,
                               verify_chain_integrity, _check_monotonic_timestamps)
- compliance._compat         (CompatibilityViolation, CompatibilityResult,
                               test_compatibility, _check_event)
"""

from __future__ import annotations

import pytest

pytest.importorskip("tracium.compliance._compat", reason="compliance submodules not yet ported to tracium")

from tracium import Event, EventType
from tracium.compliance import (
    CompatibilityResult,
    CompatibilityViolation,
    ChainIntegrityResult,
    ChainIntegrityViolation,
    IsolationResult,
    IsolationViolation,
    test_compatibility as run_compat_check,
    verify_chain_integrity,
    verify_events_scoped,
    verify_tenant_isolation,
)
from tracium.compliance._compat import _check_event
from tracium.compliance.test_chain import _check_monotonic_timestamps
from tracium.compliance.test_isolation import _check_org_disjoint
from tracium.signing import AuditStream
from tracium.ulid import generate as gen_ulid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_SECRET = "test-org-secret"
_SOURCE = "llm-trace@0.3.1"


def _make_event(**kwargs) -> Event:
    """Build a minimal valid Event, accepting keyword overrides."""
    base = {
        "event_type": EventType.TRACE_SPAN_COMPLETED,
        "source": _SOURCE,
        "payload": {"span_name": "test", "status": "ok"},
    }
    base.update(kwargs)
    return Event(**base)


def _build_signed_chain(n: int, org_id: str | None = None) -> tuple[AuditStream, list[Event]]:
    """Build a signed chain of *n* events and return (stream, signed_events)."""
    stream = AuditStream(_SECRET, _SOURCE)
    events = []
    for i in range(n):
        evt = _make_event(payload={"index": i}, org_id=org_id)
        signed = stream.append(evt)
        events.append(signed)
    return stream, events


# ===========================================================================
# IsolationViolation / IsolationResult
# ===========================================================================


class TestIsolationViolation:
    def test_frozen_fields(self) -> None:
        v = IsolationViolation(
            event_id="abc",
            violation_type="missing_org_id",
            detail="test",
        )
        assert v.event_id == "abc"
        assert v.violation_type == "missing_org_id"
        assert v.detail == "test"

    def test_frozen_immutability(self) -> None:
        v = IsolationViolation(event_id="abc", violation_type="x", detail="y")
        with pytest.raises((TypeError, AttributeError)):
            v.event_id = "other"  # type: ignore[misc]


class TestIsolationResult:
    def test_bool_true(self) -> None:
        r = IsolationResult(passed=True)
        assert bool(r) is True

    def test_bool_false(self) -> None:
        v = IsolationViolation(event_id="e", violation_type="t", detail="d")
        r = IsolationResult(passed=False, violations=[v])
        assert bool(r) is False

    def test_default_violations_empty(self) -> None:
        r = IsolationResult(passed=True)
        assert r.violations == []


# ===========================================================================
# verify_tenant_isolation
# ===========================================================================


class TestVerifyTenantIsolation:
    def test_clean_separate_orgs(self) -> None:
        """Two groups with distinct, single org_ids — no violations."""
        a = [_make_event(org_id="org-alpha") for _ in range(3)]
        b = [_make_event(org_id="org-beta") for _ in range(3)]
        result = verify_tenant_isolation(a, b)
        assert result.passed is True
        assert result.violations == []

    def test_missing_org_id_strict(self) -> None:
        """Event with org_id=None in strict mode → missing_org_id violation."""
        a = [_make_event(org_id=None)]
        b = [_make_event(org_id="org-beta")]
        result = verify_tenant_isolation(a, b, strict=True)
        assert result.passed is False
        types = [v.violation_type for v in result.violations]
        assert "missing_org_id" in types

    def test_missing_org_id_nonstrict(self) -> None:
        """Event with org_id=None in non-strict mode with no other issue → passes."""
        a = [_make_event(org_id=None)]
        b = [_make_event(org_id="org-beta")]
        result = verify_tenant_isolation(a, b, strict=False)
        # No missing_org_id violations — still passes unless there are other issues
        missing = [v for v in result.violations if v.violation_type == "missing_org_id"]
        assert missing == []

    def test_mixed_org_ids_in_same_group(self) -> None:
        """Two different org_ids in the same tenant group → mixed_org_ids violations."""
        a = [
            _make_event(org_id="org-alpha"),
            _make_event(org_id="org-zeta"),   # inconsistent
        ]
        b = [_make_event(org_id="org-beta")]
        result = verify_tenant_isolation(a, b)
        assert result.passed is False
        types = [v.violation_type for v in result.violations]
        assert "mixed_org_ids" in types

    def test_shared_org_id_between_groups(self) -> None:
        """Same org_id in both groups → shared_org_id violations."""
        a = [_make_event(org_id="org-shared")]
        b = [_make_event(org_id="org-shared")]
        result = verify_tenant_isolation(a, b)
        assert result.passed is False
        types = [v.violation_type for v in result.violations]
        assert "shared_org_id" in types

    def test_empty_groups_pass(self) -> None:
        """Empty sequences are trivially valid — no violations."""
        result = verify_tenant_isolation([], [])
        assert result.passed is True

    def test_shared_org_both_groups_flagged(self) -> None:
        """Shared org_id events are flagged in **both** tenant groups."""
        a = [_make_event(org_id="org-shared"), _make_event(org_id="org-a")]
        b = [_make_event(org_id="org-shared"), _make_event(org_id="org-b")]
        result = verify_tenant_isolation(a, b)
        shared_violations = [v for v in result.violations if v.violation_type == "shared_org_id"]
        # Two events from group A (one shared) + two from group B (one shared) — 2 total
        assert len(shared_violations) == 2


# ===========================================================================
# verify_events_scoped
# ===========================================================================


class TestVerifyEventsScoped:
    def test_no_filter_always_passes(self) -> None:
        """When neither expected value is set, every event passes."""
        events = [_make_event(org_id="org-x", team_id="team-y") for _ in range(5)]
        result = verify_events_scoped(events)
        assert result.passed is True

    def test_correct_org_and_team(self) -> None:
        events = [_make_event(org_id="org-x", team_id="team-y")]
        result = verify_events_scoped(events, expected_org_id="org-x", expected_team_id="team-y")
        assert result.passed is True

    def test_wrong_org_id(self) -> None:
        evt = _make_event(org_id="org-wrong")
        result = verify_events_scoped([evt], expected_org_id="org-right")
        assert result.passed is False
        assert result.violations[0].violation_type == "wrong_org_id"

    def test_wrong_team_id(self) -> None:
        evt = _make_event(team_id="team-wrong")
        result = verify_events_scoped([evt], expected_team_id="team-right")
        assert result.passed is False
        assert result.violations[0].violation_type == "wrong_team_id"

    def test_multiple_events_partial_failure(self) -> None:
        ok = _make_event(org_id="org-x")
        bad = _make_event(org_id="org-y")
        result = verify_events_scoped([ok, bad], expected_org_id="org-x")
        assert result.passed is False
        assert len(result.violations) == 1
        assert result.violations[0].event_id == bad.event_id


# ===========================================================================
# _check_org_disjoint (internal helper — direct coverage)
# ===========================================================================


class TestCheckOrgDisjoint:
    def test_no_overlap_returns_empty(self) -> None:
        a = [_make_event(org_id="org-a")]
        b = [_make_event(org_id="org-b")]
        violations = _check_org_disjoint(a, b)
        assert violations == []

    def test_none_org_ids_not_flagged_as_shared(self) -> None:
        """Events with org_id=None do not count as shared."""
        a = [_make_event(org_id=None)]
        b = [_make_event(org_id=None)]
        violations = _check_org_disjoint(a, b)
        assert violations == []


# ===========================================================================
# ChainIntegrityViolation / ChainIntegrityResult
# ===========================================================================


class TestChainIntegrityViolation:
    def test_fields_accessible(self) -> None:
        v = ChainIntegrityViolation(
            violation_type="tampered",
            event_id="evt-id",
            detail="HMAC mismatch",
        )
        assert v.violation_type == "tampered"
        assert v.event_id == "evt-id"
        assert v.detail == "HMAC mismatch"

    def test_event_id_optional(self) -> None:
        v = ChainIntegrityViolation(violation_type="gap", event_id=None, detail="x")
        assert v.event_id is None


class TestChainIntegrityResult:
    def test_bool_true(self) -> None:
        r = ChainIntegrityResult(passed=True, chain_result=None, violations=[])
        assert bool(r) is True

    def test_bool_false(self) -> None:
        v = ChainIntegrityViolation(violation_type="tampered", event_id="e", detail="d")
        r = ChainIntegrityResult(passed=False, chain_result=None, violations=[v])
        assert bool(r) is False


# ===========================================================================
# verify_chain_integrity
# ===========================================================================


class TestVerifyChainIntegrity:
    def test_empty_events(self) -> None:
        result = verify_chain_integrity([], _SECRET)
        assert result.passed is True
        assert result.chain_result is None
        assert result.events_verified == 0
        assert result.gaps_detected == 0

    def test_valid_single_event(self) -> None:
        _, events = _build_signed_chain(1)
        result = verify_chain_integrity(events, _SECRET)
        assert result.passed is True
        assert result.events_verified == 1
        assert result.gaps_detected == 0

    def test_valid_multi_event_chain(self) -> None:
        _, events = _build_signed_chain(5)
        result = verify_chain_integrity(events, _SECRET)
        assert result.passed is True
        assert result.events_verified == 5
        assert result.gaps_detected == 0

    def test_tampered_event(self) -> None:
        """Tampering the payload of a signed event causes a tampered violation."""
        _, events = _build_signed_chain(3)
        # Tamper with the second event's payload (signature no longer valid)
        tampered = events[1]
        object.__setattr__(tampered, "_payload", {"hacked": True})
        result = verify_chain_integrity(events, _SECRET)
        assert result.passed is False
        tampered_violations = [v for v in result.violations if v.violation_type == "tampered"]
        assert len(tampered_violations) == 1
        assert tampered_violations[0].event_id == tampered.event_id

    def test_gap_only_no_tamper_violation(self) -> None:
        """Missing event in the middle → gap violation only, no tamper violation."""
        _, events = _build_signed_chain(3)
        # e0, e2 — skip e1 (e2.prev_id points to e1, not e0)
        chain_with_gap = [events[0], events[2]]
        result = verify_chain_integrity(chain_with_gap, _SECRET)
        assert result.passed is False
        # Must have a gap violation
        gap_violations = [v for v in result.violations if v.violation_type == "gap"]
        assert len(gap_violations) == 1
        assert gap_violations[0].event_id == events[2].event_id
        # Must NOT have a tamper violation (events are individually valid)
        tamper_violations = [v for v in result.violations if v.violation_type == "tampered"]
        assert tamper_violations == []
        assert result.gaps_detected == 1

    def test_non_monotonic_timestamps(self) -> None:
        """Non-monotonic timestamps are flagged by default."""
        _, events = _build_signed_chain(2)
        # Tamper the second event's timestamp to be in the past
        # (timestamp is NOT part of the HMAC, so the signature remains valid)
        object.__setattr__(events[1], "_timestamp", "2000-01-01T00:00:00.000000Z")
        result = verify_chain_integrity(events, _SECRET)
        # Chain itself should still be cryptographically valid
        assert result.chain_result is not None
        ts_violations = [
            v for v in result.violations if v.violation_type == "non_monotonic_timestamp"
        ]
        assert len(ts_violations) == 1
        assert ts_violations[0].event_id == events[1].event_id

    def test_check_monotonic_timestamps_false(self) -> None:
        """When check_monotonic_timestamps=False no timestamp violations are added."""
        _, events = _build_signed_chain(2)
        object.__setattr__(events[1], "_timestamp", "2000-01-01T00:00:00.000000Z")
        result = verify_chain_integrity(events, _SECRET, check_monotonic_timestamps=False)
        ts_violations = [
            v for v in result.violations if v.violation_type == "non_monotonic_timestamp"
        ]
        assert ts_violations == []


# ===========================================================================
# _check_monotonic_timestamps (direct coverage)
# ===========================================================================


class TestCheckMonotonicTimestamps:
    def test_monotonic_returns_empty(self) -> None:
        """Ascending timestamps → no violations."""
        _, events = _build_signed_chain(3)
        # AuditStream generates real-time timestamps — all ascending
        violations = _check_monotonic_timestamps(events)
        assert violations == []

    def test_single_event_returns_empty(self) -> None:
        _, events = _build_signed_chain(1)
        violations = _check_monotonic_timestamps(events)
        assert violations == []


# ===========================================================================
# CompatibilityViolation / CompatibilityResult
# ===========================================================================


class TestCompatibilityViolation:
    def test_fields_accessible(self) -> None:
        v = CompatibilityViolation(
            check_id="CHK-1",
            rule="Required fields present",
            detail="source is empty",
            event_id="evt-1",
        )
        assert v.check_id == "CHK-1"
        assert v.rule == "Required fields present"
        assert v.detail == "source is empty"
        assert v.event_id == "evt-1"


class TestCompatibilityResult:
    def test_bool_true(self) -> None:
        r = CompatibilityResult(passed=True, events_checked=1)
        assert bool(r) is True

    def test_bool_false(self) -> None:
        v = CompatibilityViolation(check_id="CHK-5", rule="r", detail="d", event_id="e")
        r = CompatibilityResult(passed=False, events_checked=1, violations=[v])
        assert bool(r) is False


# ===========================================================================
# test_compatibility / _check_event
# ===========================================================================


class TestTestCompatibility:
    def test_valid_event_passes_all_checks(self) -> None:
        """A fully valid event produces no violations."""
        evt = _make_event()
        result = run_compat_check([evt])
        assert result.passed is True
        assert result.events_checked == 1
        assert result.violations == []

    def test_registered_event_type_passes_chk2(self) -> None:
        """Registered EventType skips validate_custom — no CHK-2 violation."""
        evt = Event(
            event_type=EventType.TRACE_SPAN_COMPLETED,
            source=_SOURCE,
            payload={"span_name": "ok"},
        )
        result = run_compat_check([evt])
        chk2 = [v for v in result.violations if v.check_id == "CHK-2"]
        assert chk2 == []

    def test_valid_custom_event_type_passes_chk2(self) -> None:
        """Valid custom x.* type is unregistered but passes validate_custom."""
        evt = Event(
            event_type="x.mycompany.inference.completed",
            source=_SOURCE,
            payload={"result": "ok"},
        )
        result = run_compat_check([evt])
        chk2 = [v for v in result.violations if v.check_id == "CHK-2"]
        assert chk2 == []

    def test_invalid_event_type_chk2_violation(self) -> None:
        """Unregistered type in a reserved namespace triggers CHK-2."""
        evt = _make_event()
        # "llm.trace" is reserved, but this type string is not in the registry
        # → is_registered returns False, validate_custom raises EventTypeError
        object.__setattr__(evt, "_event_type", "llm.trace.not.existing")
        violations = _check_event(evt)
        chk2 = [v for v in violations if v.check_id == "CHK-2"]
        assert len(chk2) == 1
        assert "CHK-2" == chk2[0].check_id

    def test_bad_source_pattern_chk3_violation(self) -> None:
        """Source that doesn't match the semver pattern triggers CHK-3."""
        evt = _make_event()
        # Use source that lacks @semver
        object.__setattr__(evt, "_source", "no-version-here")
        violations = _check_event(evt)
        chk3 = [v for v in violations if v.check_id == "CHK-3"]
        assert len(chk3) == 1

    def test_bad_event_id_chk5_violation(self) -> None:
        """Non-ULID event_id triggers CHK-5."""
        evt = _make_event()
        object.__setattr__(evt, "_event_id", "not-a-valid-ulid-at-all!!")
        violations = _check_event(evt)
        chk5 = [v for v in violations if v.check_id == "CHK-5"]
        assert len(chk5) == 1

    def test_empty_schema_version_chk1_violation(self) -> None:
        """Empty schema_version triggers CHK-1."""
        evt = _make_event()
        object.__setattr__(evt, "_schema_version", "")
        violations = _check_event(evt)
        chk1 = [v for v in violations if v.check_id == "CHK-1" and "schema_version" in v.detail]
        assert len(chk1) == 1

    def test_empty_source_chk1_violation(self) -> None:
        """Empty source triggers CHK-1 (skips CHK-3 due to falsy guard)."""
        evt = _make_event()
        object.__setattr__(evt, "_source", "")
        violations = _check_event(evt)
        chk1 = [v for v in violations if v.check_id == "CHK-1" and "source" in v.detail]
        assert len(chk1) == 1
        # CHK-3 must NOT fire when source is empty (short-circuited)
        chk3 = [v for v in violations if v.check_id == "CHK-3"]
        assert chk3 == []

    def test_empty_payload_chk1_violation(self) -> None:
        """Empty payload dict triggers CHK-1."""
        evt = _make_event()
        object.__setattr__(evt, "_payload", {})
        violations = _check_event(evt)
        chk1 = [v for v in violations if v.check_id == "CHK-1" and "payload" in v.detail]
        assert len(chk1) == 1

    def test_multiple_events_counted(self) -> None:
        """events_checked reflects the full batch size."""
        events = [_make_event() for _ in range(4)]
        result = run_compat_check(events)
        assert result.events_checked == 4

    def test_empty_batch(self) -> None:
        """Empty batch produces a passed result with 0 events checked."""
        result = run_compat_check([])
        assert result.passed is True
        assert result.events_checked == 0
