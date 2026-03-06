# llm.audit — Audit Chain Events

> **Auto-documented module:** `agentobs.namespaces.audit`

The `llm.audit.*` namespace records HMAC signing-key lifecycle events and the
results of audit-chain verification runs (RFC-0001 §11).  These events allow
operators to reconstruct a tamper-evident history of key rotations and to
log the outcome of every chain-integrity check.

## Payload classes

| Class | Event type | Description |
|-------|-----------|-------------|
| `AuditKeyRotatedPayload` | `llm.audit.key.rotated` | An HMAC signing key was rotated |
| `AuditChainVerifiedPayload` | `llm.audit.chain.verified` | An audit chain segment was verified intact |
| `AuditChainTamperedPayload` | `llm.audit.chain.tampered` | Tampering or a gap was detected in the audit chain |

---

## `AuditKeyRotatedPayload`

Records that an HMAC signing key was replaced.  `effective_from_event_id` is
the ULID of the first event signed with the new key, enabling exact replay
of any chain segment.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `key_id` | `str` | ✓ | Identifier of the new key |
| `previous_key_id` | `str` | ✓ | Identifier of the superseded key |
| `rotated_at` | `str` | ✓ | ISO 8601 timestamp (6 decimal places) |
| `rotated_by` | `str` | ✓ | Identity of the operator or service that rotated the key |
| `rotation_reason` | `str \| None` | — | One of `"scheduled"`, `"suspected_compromise"`, `"policy_update"`, `"key_expiry"`, `"manual"` |
| `key_algorithm` | `str` | — | Defaults to `"HMAC-SHA256"` |
| `effective_from_event_id` | `str \| None` | — | ULID of first event signed with the new key |

### Example

```python
from agentobs import Event, EventType
from agentobs.namespaces.audit import AuditKeyRotatedPayload

payload = AuditKeyRotatedPayload(
    key_id="key_01HX_v2",
    previous_key_id="key_01HX_v1",
    rotated_at="2026-03-04T12:00:00.000000Z",
    rotated_by="ops-bot@agentobs.io",
    rotation_reason="scheduled",
)

event = Event(
    event_type=EventType.AUDIT_KEY_ROTATED,
    source="key-manager@1.0.0",
    org_id="org_01HX",
    payload=payload.to_dict(),
)
```

---

## `AuditChainVerifiedPayload`

Records that a segment of the audit chain was checked and found intact.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `verified_from_event_id` | `str` | ✓ | ULID of the first event in the verified range |
| `verified_to_event_id` | `str` | ✓ | ULID of the last event in the verified range |
| `event_count` | `int` | ✓ | Number of events verified |
| `verified_at` | `str` | ✓ | ISO 8601 timestamp of the verification run |
| `verified_by` | `str` | ✓ | Identity of the verifier (service or operator) |

### Example

```python
from agentobs import Event, EventType
from agentobs.namespaces.audit import AuditChainVerifiedPayload

payload = AuditChainVerifiedPayload(
    verified_from_event_id="01HXABC0000000000000000000",
    verified_to_event_id="01HXABCZZZZZZZZZZZZZZZZZZZ",
    event_count=1024,
    verified_at="2026-03-04T14:00:00.000000Z",
    verified_by="audit-worker@1.0.0",
)

event = Event(
    event_type=EventType.AUDIT_CHAIN_VERIFIED,
    source="audit-worker@1.0.0",
    org_id="org_01HX",
    payload=payload.to_dict(),
)
```

---

## `AuditChainTamperedPayload`

Records that tampering or a sequence gap was detected when verifying the audit
chain.  `severity` guides incident-response triage.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `first_tampered_event_id` | `str` | ✓ | ULID of the first event with a broken HMAC |
| `tampered_count` | `int` | ✓ | Number of events with invalid signatures |
| `detected_at` | `str` | ✓ | ISO 8601 timestamp of detection |
| `detected_by` | `str` | ✓ | Identity of the detector |
| `gap_count` | `int \| None` | — | Number of missing sequence IDs |
| `gap_prev_ids` | `list[str]` | — | ULIDs immediately before each detected gap |
| `severity` | `str \| None` | — | `"low"`, `"medium"`, `"high"`, or `"critical"` |

### Example

```python
from agentobs import Event, EventType
from agentobs.namespaces.audit import AuditChainTamperedPayload

payload = AuditChainTamperedPayload(
    first_tampered_event_id="01HXDEF0000000000000000000",
    tampered_count=3,
    detected_at="2026-03-04T15:30:00.000000Z",
    detected_by="audit-worker@1.0.0",
    severity="high",
    gap_count=1,
    gap_prev_ids=["01HXDEE0000000000000000000"],
)

event = Event(
    event_type=EventType.AUDIT_CHAIN_TAMPERED,
    source="audit-worker@1.0.0",
    org_id="org_01HX",
    payload=payload.to_dict(),
)
```
